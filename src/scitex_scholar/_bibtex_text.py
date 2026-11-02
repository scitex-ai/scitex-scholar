"""Encode plain bibliographic text for LaTeX, not identifiers or URLs."""

import re

# Preserve only safe escapes emitted here; arbitrary TeX commands are text.
_ESCAPED = re.compile(r"\\(?:[&%$#_{}]|text(?:backslash|asciitilde|asciicircum)\{\})")
_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "\\": r"\textbackslash{}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape_plain_text(text, *, limit=None):
    """Escape normalized plain text once, preserving Unicode and punctuation."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[:limit] + "..."
    output, index = [], 0
    while index < len(text):
        existing = _ESCAPED.match(text, index)
        if existing:
            output.append(existing.group())
            index = existing.end()
        else:
            output.append(_SPECIAL.get(text[index], text[index]))
            index += 1
    return "".join(output)
