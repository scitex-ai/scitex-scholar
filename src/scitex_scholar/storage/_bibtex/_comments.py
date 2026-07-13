#!/usr/bin/env python3
# File: src/scitex_scholar/storage/_bibtex/_comments.py
"""Safe emission of ``%`` header comments in generated BibTeX files."""

from __future__ import annotations

__all__ = ["BIBTEX_AT_REPLACEMENT", "sanitize_bibtex_comments"]

BIBTEX_AT_REPLACEMENT = "(at)"


def sanitize_bibtex_comments(content: str) -> str:
    """Neutralize raw ``@`` characters in every ``%`` comment line of *content*.

    BibTeX parsers locate entries by scanning for ``@`` and do **not** honour
    ``%`` as a comment introducer. A raw ``@`` in a header comment — an email
    address, a handle, an ``@``-bearing source filename — is therefore read as
    the start of a malformed entry and aborts the parse of an otherwise valid
    file. Replacing it with ``(at)`` keeps the header readable while making the
    output re-parseable.

    Only lines whose first non-space character is ``%`` are rewritten, so entry
    lines (``@article{...``) and field values pass through untouched.

    Args:
        content: Full BibTeX file content.

    Returns:
        The same content with ``@`` replaced by ``(at)`` inside comment lines.
    """
    return "\n".join(
        (
            line.replace("@", BIBTEX_AT_REPLACEMENT)
            if line.lstrip().startswith("%")
            else line
        )
        for line in content.split("\n")
    )


# EOF
