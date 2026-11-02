"""Bounded reads and no-overwrite publication for explicit example jobs."""

import contextlib
import fcntl
import json
import os
import time
from pathlib import Path


class ShowcaseConflict(ValueError):
    """Existing library content cannot safely admit this additive example."""


def checked(path, root, *, directory=False):
    path, root = Path(path), Path(root)
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ShowcaseConflict(
            "Example target must remain inside its authorized library"
        )
    if path.exists() and (not path.is_dir() if directory else not path.is_file()):
        raise ShowcaseConflict("Existing example target has an incompatible type")
    return path


def read_json(path):
    if path.stat().st_size > 2_000_000:
        raise ShowcaseConflict(
            "Existing metadata is too large for bounded example admission"
        )
    try:
        obj = json.loads(path.read_text())
    except (ValueError, UnicodeError) as exc:
        raise ShowcaseConflict(
            "Existing metadata must be preserved and repaired"
        ) from exc
    if not isinstance(obj, dict):
        raise ShowcaseConflict("Existing metadata must be a mapping")
    return obj


def entries(directory):
    if not directory.exists():
        return []
    result = []
    for entry in directory.iterdir():
        result.append(entry)
        if len(result) > 10_000:
            raise ShowcaseConflict("Library exceeds the bounded example inventory")
    return sorted(result)


@contextlib.contextmanager
def locked(root):
    path = checked(root / ".mnist-showcase.lock", root)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Another example job still owns the library lock"
                    )
                time.sleep(0.02)
        yield
    finally:
        os.close(descriptor)


def publish_json(path, payload, root):
    """Publish a complete new file, never replace existing bytes."""
    import tempfile

    path = checked(path, root)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".mnist-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
