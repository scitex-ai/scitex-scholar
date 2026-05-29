#!/usr/bin/env python3
"""Per-edge INTEGRATION + DEGRADATION tests (scitex-clew edge).

This file mirrors the canonical SciTeX optional-edge template
(scitex-io ``tests/integration/test_figrecipe_edge.py``). It exercises
scitex-scholar's wiring into the OPTIONAL ``scitex-clew`` collaborator.

The edge under test
-------------------
``scitex_scholar.storage.PaperIO.save_pdf(pdf_path)`` copies the PDF into the
paper's MASTER directory and records ``pdf_size_bytes``. As an OPTIONAL
provenance step it then lazily ``import scitex_clew`` and stamps
``paper.container.pdf_sha256`` with ``scitex_clew.hash_file(dest)``. When clew
is installed the hash field is populated; when clew is absent the import fails
and ``save_pdf`` must degrade gracefully — the PDF still lands on disk,
``pdf_size_bytes`` is still recorded, and ``pdf_sha256`` stays ``None`` rather
than the caller seeing an ``ImportError``.

NB on the seam vs. this file: ``save_pdf`` exposes a ``clew_module`` test seam
(``tests/integration/test_clew_integration.py`` drives it). This file is the
complementary *edge* template — it exercises the REAL default lazy-import path
(no ``clew_module`` kwarg), proving the production code path itself, both with
clew genuinely importable and with clew genuinely evicted from ``sys.modules``.

The two test kinds every optional edge should have
--------------------------------------------------
1. INTEGRATION (collaborator PRESENT): exercise the real collaborator and
   assert on the concrete artifact it produces (the populated SHA-256). Guard
   with ``pytest.importorskip("scitex_clew")`` so minimal installs stay green.

2. DEGRADATION (collaborator ABSENT): simulate the dependency being missing in
   a hermetic, reversible way (a fixture that snapshots ``sys.modules``, shadows
   ``scitex_clew`` so a fresh ``import scitex_clew`` raises ImportError, and
   restores the exact module table on teardown), then assert ``save_pdf`` keeps
   working through its documented graceful contract.

Conventions honoured (so this stays a clean template):
  - One assertion per test: shared expensive setup is lifted into a fixture;
    each behaviour gets its own named, single-assert test, so a red CI line
    names exactly what broke.
  - Explicit Arrange / Act / Assert markers in every test.
  - No ``monkeypatch`` / ``mocker``: the clew-absent fixture hand-swaps
    ``sys.modules`` and restores it on teardown.

Empirically verified contract
------------------------------
clew PRESENT  : ``pdf_sha256`` == ``scitex_clew.hash_file(dest)`` (a non-empty
                lowercase hex digest), PDF copied, ``pdf_size_bytes`` recorded.
clew ABSENT   : PDF still copied, ``pdf_size_bytes`` recorded, ``pdf_sha256``
                stays ``None``, no exception escapes ``save_pdf``.
"""

from __future__ import annotations

import importlib
import sys

import pytest

# ===========================================================================
# 1. INTEGRATION  —  scitex_clew PRESENT
# ===========================================================================
scitex_clew = pytest.importorskip("scitex_clew")


class _SavedPdf:
    """The artifacts a save_pdf() produced (lifted shared setup)."""

    def __init__(self, paper, dest, expected_hash):
        self.paper = paper
        self.dest = dest
        self.expected_hash = expected_hash


@pytest.fixture
def saved_pdf_with_clew(tmp_path):
    """save_pdf() a real PDF with clew importable; yield the resulting state.

    Uses the REAL default lazy-import path (no ``clew_module`` kwarg) so the
    production provenance code is what gets exercised.
    """
    from scitex_scholar.core.Paper import Paper
    from scitex_scholar.storage.PaperIO import PaperIO

    src = tmp_path / "src.pdf"
    src.write_bytes(b"%PDF-1.4 fake content for hash test\n")
    expected_hash = scitex_clew.hash_file(src)

    paper = Paper()
    paper.container.library_id = "DEADBEEF"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    dest = io.save_pdf(src)
    return _SavedPdf(paper, dest, expected_hash)


def test_save_pdf_with_clew_copies_pdf(saved_pdf_with_clew):
    """The PDF is copied into the paper's MASTER directory."""
    # Arrange
    out = saved_pdf_with_clew
    # Act
    exists = out.dest.exists()
    # Assert
    assert exists


def test_save_pdf_with_clew_records_size_bytes(saved_pdf_with_clew):
    """pdf_size_bytes records the copied file's byte length."""
    # Arrange
    out = saved_pdf_with_clew
    # Act
    size = out.paper.container.pdf_size_bytes
    # Assert
    assert size == out.dest.stat().st_size


def test_save_pdf_with_clew_populates_sha256(saved_pdf_with_clew):
    """pdf_sha256 is stamped via the real scitex_clew.hash_file path."""
    # Arrange
    out = saved_pdf_with_clew
    # Act
    digest = out.paper.container.pdf_sha256
    # Assert
    assert digest == out.expected_hash


def test_save_pdf_with_clew_sha256_is_nonempty_hex(saved_pdf_with_clew):
    """The stamped hash is a non-empty lowercase hex digest."""
    # Arrange
    out = saved_pdf_with_clew
    # Act
    digest = out.paper.container.pdf_sha256
    # Assert
    assert digest and all(c in "0123456789abcdef" for c in digest)


# ===========================================================================
# 2. DEGRADATION  —  scitex_clew ABSENT
# ===========================================================================
@pytest.fixture
def scitex_clew_absent():
    """Make ``import scitex_clew`` fail for the duration of the test.

    Hermetic and reversible:
      1. snapshot the whole ``sys.modules`` so teardown can restore it exactly;
      2. evict ``scitex_clew`` (and the PaperIO module that performs the lazy
         import) from the module table, then shadow ``scitex_clew`` with
         ``None`` so a *fresh* ``import scitex_clew`` raises ImportError;
      3. reload ``scitex_scholar.storage.PaperIO`` so the class under test is
         the freshly imported one — its ``save_pdf`` body runs ``import
         scitex_clew`` at call time, which now fails, driving the degradation
         branch.

    Yields the freshly reloaded ``PaperIO`` class.
    """
    # Ensure importable before we tear it down.
    import scitex_scholar.storage.PaperIO  # noqa: F401

    # 1. Full snapshot for an exact restore.
    snapshot = dict(sys.modules)

    # 2. Evict scitex_clew + the PaperIO module, then block scitex_clew so a
    #    fresh import raises ImportError (a None entry in sys.modules makes
    #    ``import scitex_clew`` raise "import of scitex_clew halted; None in
    #    sys.modules", which is an ImportError subclass — exactly the failure
    #    save_pdf's ``except ImportError`` guard is written to catch).
    def _to_evict(name: str) -> bool:
        return (
            name == "scitex_clew"
            or name.startswith("scitex_clew.")
            or name == "scitex_scholar.storage.PaperIO"
        )

    for name in [n for n in list(sys.modules) if _to_evict(n)]:
        del sys.modules[name]
    sys.modules["scitex_clew"] = None  # type: ignore[assignment]
    reloaded = importlib.import_module("scitex_scholar.storage.PaperIO")

    try:
        yield reloaded.PaperIO
    finally:
        # Restore the exact pre-test module table.
        for name in list(sys.modules):
            if name not in snapshot:
                del sys.modules[name]
        sys.modules.update(snapshot)


def test_clew_absent_fixture_blocks_the_import(scitex_clew_absent):
    """Sanity: under the fixture, ``import scitex_clew`` really does fail."""
    # Arrange
    _ = scitex_clew_absent
    # Act
    module_name = "scitex_clew"
    # Assert
    with pytest.raises(ImportError):
        importlib.import_module(module_name)


@pytest.fixture
def saved_pdf_without_clew(scitex_clew_absent, tmp_path):
    """save_pdf() a real PDF with clew evicted; yield the resulting state."""
    from scitex_scholar.core.Paper import Paper

    PaperIO = scitex_clew_absent

    src = tmp_path / "src.pdf"
    src.write_bytes(b"fake-pdf-bytes")
    paper = Paper()
    paper.container.library_id = "CAFEBABE"
    io = PaperIO(paper=paper, base_dir=tmp_path / "master")
    dest = io.save_pdf(src)
    return _SavedPdf(paper, dest, None)


def test_save_pdf_without_clew_still_copies_pdf(saved_pdf_without_clew):
    """The PDF copy is unaffected by clew's absence."""
    # Arrange
    out = saved_pdf_without_clew
    # Act
    exists = out.dest.exists()
    # Assert
    assert exists


def test_save_pdf_without_clew_records_size_bytes(saved_pdf_without_clew):
    """pdf_size_bytes is still recorded without clew."""
    # Arrange
    out = saved_pdf_without_clew
    # Act
    size = out.paper.container.pdf_size_bytes
    # Assert
    assert size == len(b"fake-pdf-bytes")


def test_save_pdf_without_clew_leaves_sha256_none(saved_pdf_without_clew):
    """The provenance hash degrades to None — that field requires clew."""
    # Arrange
    out = saved_pdf_without_clew
    # Act
    digest = out.paper.container.pdf_sha256
    # Assert
    assert digest is None
