"""Real primary-file admission, preservation and explicit dry-run behavior."""

import hashlib
import json
import multiprocessing
import os
from pathlib import Path

import pytest

from scitex_scholar.showcase import (
    mnist_reference_bibtex,
    mnist_references,
    seed_mnist_library,
)
from scitex_scholar.showcase._catalog import identifier
from scitex_scholar.showcase._files import ShowcaseConflict

PROJECT = "example-project-mnist"


def _publishing_worker(root, paused, release, results):
    """Hold the real publication between directory creation and metadata link."""
    original = os.link
    intercepted = False

    def link(source, destination, *args, **kwargs):
        nonlocal intercepted
        path = Path(destination)
        if (
            not intercepted
            and path.name == "metadata.json"
            and path.parent.parent == root / "MASTER"
        ):
            intercepted = True
            paused.set()
            if not release.wait(15):
                raise TimeoutError("Owned publication fixture was not released")
        return original(source, destination, *args, **kwargs)

    os.link = link
    try:
        result = seed_mnist_library(root, project=PROJECT, dry_run=False)
        results.put((result["new_papers"], result["new_memberships"]))
    except Exception as error:
        results.put(type(error).__name__)
    finally:
        os.link = original


def _waiting_worker(root, attempted, results):
    """Observe a real second writer's lock attempt in its own child process."""
    import fcntl

    original = fcntl.flock

    def flock(descriptor, operation):
        attempted.set()
        return original(descriptor, operation)

    fcntl.flock = flock
    try:
        result = seed_mnist_library(root, project=PROJECT, dry_run=False)
        results.put((result["new_papers"], result["new_memberships"]))
    except Exception as error:
        results.put(type(error).__name__)
    finally:
        fcntl.flock = original


def test_second_writer_waits_for_incomplete_locked_publication(tmp_path):
    # Arrange: the first real writer has made a directory, not its metadata yet.
    root = tmp_path / "library"
    context = multiprocessing.get_context("fork")
    paused, release, attempted = (context.Event() for _ in range(3))
    results = context.Queue()
    first = context.Process(
        target=_publishing_worker, args=(root, paused, release, results)
    )
    second = context.Process(target=_waiting_worker, args=(root, attempted, results))
    first.start()
    second_started = False
    try:
        if not paused.wait(10):
            raise TimeoutError("First writer did not reach the publication boundary")
        # Act: the second must acquire the library lock before reading that state.
        second.start()
        second_started = True
        waited = attempted.wait(10)
        release.set()
        actual = [results.get(timeout=15), results.get(timeout=15)]
        first.join(timeout=10)
        second.join(timeout=10)
        # Assert: no spurious collision or duplicate publication is admitted.
        assert (waited, sorted(actual, key=str), first.exitcode, second.exitcode) == (
            True,
            [(0, 0), (4, 4)],
            0,
            0,
        )
    finally:
        release.set()
        for process in [first, second] if second_started else [first]:
            if process.is_alive():
                process.terminate()
            process.join(timeout=10)
        results.close()
        results.join_thread()


def snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        name = str(p.relative_to(root))
        if p.is_symlink():
            result[name] = ["symlink", str(p.readlink())]
        elif p.is_file():
            result[name] = ["file", hashlib.sha256(p.read_bytes()).hexdigest()]
        else:
            result[name] = ["directory"]
    return result


def refused(root, project):
    """Observe the exact expected refusal without hiding unexpected failures."""
    try:
        seed_mnist_library(root, project=project, dry_run=False)
    except ShowcaseConflict:
        return True
    return False


def test_missing_library_dry_run_creates_nothing(tmp_path):
    # Arrange
    root = tmp_path / "new-library"
    before = snapshot(tmp_path)
    # Act
    result = seed_mnist_library(root, project=PROJECT)
    # Assert
    assert (result["new_papers"], result["new_memberships"], snapshot(tmp_path)) == (
        4,
        4,
        before,
    )


def test_apply_uses_real_primary_schema_and_second_apply_is_byte_idempotent(tmp_path):
    # Arrange
    root = tmp_path / "library"
    # Act
    first = seed_mnist_library(root, project=PROJECT, dry_run=False)
    before = snapshot(root)
    second = seed_mnist_library(root, project=PROJECT, dry_run=False)
    data = [
        json.loads((root / "MASTER" / n / "metadata.json").read_text())
        for n in first["paper_ids"]
    ]
    # Assert
    assert (
        first["new_papers"],
        first["new_memberships"],
        second["new_papers"],
        second["new_memberships"],
        snapshot(root) == before,
        all(d["container"]["projects"] == [PROJECT] for d in data),
        all(d["metadata"]["basic"]["abstract"] is None for d in data),
        all(d["metadata"]["citation_count"]["total"] is None for d in data),
        all(
            (root / PROJECT / n).resolve() == root / "MASTER" / n
            for n in first["paper_ids"]
        ),
    ) == (4, 4, 0, 0, True, True, True, True, True)


def test_existing_user_record_and_readable_membership_are_preserved(tmp_path):
    # Arrange
    root = tmp_path / "library"
    record = root / "MASTER" / "CUSTOM01"
    record.mkdir(parents=True)
    existing = {
        "metadata": {
            "id": {"doi": mnist_references()[0]["doi"]},
            "basic": {"title": "My edited title"},
        },
        "container": {"projects": ["another-project"]},
        "private_user_note": "Preserve this byte for byte",
    }
    (record / "metadata.json").write_text(json.dumps(existing))
    (record / "reading-notes.txt").write_text("An existing user annotation")
    pdir = root / PROJECT
    pdir.mkdir()
    (pdir / "My readable citation").symlink_to(Path("../MASTER/CUSTOM01"))
    before = snapshot(record)
    # Act
    result = seed_mnist_library(root, project=PROJECT, dry_run=False)
    # Assert
    assert (
        result["new_papers"],
        result["new_memberships"],
        result["paper_ids"][0],
        snapshot(record),
        (pdir / "My readable citation").is_symlink(),
        (pdir / "CUSTOM01").exists(),
    ) == (3, 3, "CUSTOM01", before, True, False)


@pytest.mark.parametrize(
    "project",
    [
        "",
        "..",
        ".",
        "../outside",
        "owner/project",
        "/tmp/outside",
        "x\\y",
        "MASTER",
        "downloads",
    ],
)
def test_unsafe_project_refuses_before_any_write(tmp_path, project):
    # Arrange
    before = snapshot(tmp_path)
    # Act
    was_refused = refused(tmp_path / "library", project)
    # Assert
    assert (was_refused, snapshot(tmp_path)) == (True, before)


@pytest.mark.parametrize("part", ["MASTER", PROJECT])
def test_escaping_directory_symlinks_are_refused(tmp_path, part):
    # Arrange
    root, outside = tmp_path / "library", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("Existing owned fixture")
    (root / part).symlink_to(outside, target_is_directory=True)
    before = snapshot(tmp_path)
    # Act
    was_refused = refused(root, PROJECT)
    # Assert
    assert (was_refused, snapshot(tmp_path)) == (True, before)


def test_conflicting_generated_id_preserves_every_existing_file(tmp_path):
    # Arrange
    root = tmp_path / "library"
    target = root / "MASTER" / identifier(mnist_references()[0])
    target.mkdir(parents=True)
    (target / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "id": {"doi": "10.9999/owned-conflicting-fixture"},
                    "basic": {"title": "Existing unrelated fixture"},
                }
            }
        )
    )
    before = snapshot(tmp_path)
    # Act
    was_refused = refused(root, PROJECT)
    # Assert
    assert (was_refused, snapshot(tmp_path)) == (True, before)


def test_bibtex_export_contains_only_verified_references():
    # Arrange
    refs = mnist_references()
    # Act
    bib = mnist_reference_bibtex()
    # Assert
    assert (
        len(refs),
        bib.count("@article{"),
        "example.2020" in bib,
        "abstract =" in bib,
        refs[1]["doi"],
        all(ref["sources"] for ref in refs),
    ) == (4, 4, False, False, None, True)


@pytest.fixture(
    params=["metadata-link", "lock-link", "manifest-conflict", "membership-conflict"]
)
def conflicting_state(tmp_path, request):
    """Own each concrete conflicting filesystem state for preservation checks."""
    kind = request.param
    root = tmp_path / "library"
    master = root / "MASTER"
    project = root / PROJECT
    master.mkdir(parents=True)
    project.mkdir()
    outside = tmp_path / "keep.json"
    outside.write_text('{"owned": "preserved"}')
    if kind == "metadata-link":
        folder = master / "CUSTOM01"
        folder.mkdir()
        (folder / "metadata.json").symlink_to(outside)
    elif kind == "lock-link":
        (root / ".mnist-showcase.lock").symlink_to(outside)
    elif kind == "manifest-conflict":
        (project / ".mnist-showcase-v1.json").write_text('{"owned": "preserved"}')
    else:
        (project / identifier(mnist_references()[0])).write_text("Existing user entry")
    before = snapshot(tmp_path)
    return root, before


def test_existing_conflicts_and_links_are_not_replaced(tmp_path, conflicting_state):
    # Arrange
    root, before = conflicting_state
    # Act
    was_refused = refused(root, PROJECT)
    # Assert
    assert (was_refused, snapshot(tmp_path)) == (True, before)


def test_reserved_name_definition_is_shared_with_existing_reconciliation():
    # Arrange
    from scitex_scholar._library_names import RESERVED_LIBRARY_DIRS
    from scitex_scholar.storage import _project_reconcile

    # Act
    same_owner = _project_reconcile.RESERVED_LIBRARY_DIRS is RESERVED_LIBRARY_DIRS
    # Assert
    assert same_owner


def test_unresolved_user_metadata_is_preserved_without_inventing_an_identity(tmp_path):
    # Arrange
    root = tmp_path / "library"
    record = root / "MASTER" / "UNKNOWN1"
    record.mkdir(parents=True)
    (record / "metadata.json").write_text('{"metadata": {}, "user_note": "keep"}')
    before = snapshot(record)
    # Act
    result = seed_mnist_library(root, project=PROJECT, dry_run=False)
    # Assert
    assert (result["new_papers"], snapshot(record)) == (4, before)
