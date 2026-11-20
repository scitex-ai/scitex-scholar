"""Open a saved PDF from a single Scholar library record."""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path
from stat import S_ISREG
from typing import BinaryIO


def open_library_pdf(root: Path, library_id: str) -> BinaryIO | None:
    """Open a PDF under an already validated library ID without following links."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        try:
            parent = os.open(root, directory_flags)
            stack.callback(os.close, parent)
            for part in ("MASTER", library_id):
                parent = os.open(part, directory_flags, dir_fd=parent)
                stack.callback(os.close, parent)
            metadata = os.stat("metadata.json", dir_fd=parent, follow_symlinks=False)
            if not S_ISREG(metadata.st_mode):
                return None
            names = sorted(
                name
                for name in os.listdir(parent)
                if name.lower().endswith(".pdf")
                and not name.lower().startswith(("supple-", "additional-", "notes-"))
                and name.lower() != "download-tmp.pdf"
            )
        except OSError:
            return None

        for name in names:
            try:
                fd = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                )
            except OSError:
                continue
            if not S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                continue
            stream = os.fdopen(fd, "rb")
            try:
                if stream.read(5) == b"%PDF-":
                    stream.seek(0)
                    return stream
            except OSError:
                stream.close()
                continue
            stream.close()
    return None
