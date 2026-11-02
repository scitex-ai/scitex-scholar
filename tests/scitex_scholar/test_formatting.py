"""BibTeX plain text must typeset literally, without changing identifiers."""

import pytest

from scitex_scholar.formatting import to_bibtex, to_ris


@pytest.mark.parametrize(
    "text,escaped",
    [
        ("A & B", r"A \& B"),
        ("50%", r"50\%"),
        ("value_1", r"value\_1"),
        ("#topic", r"\#topic"),
        ("$value", r"\$value"),
        ("{literal}", r"\{literal\}"),
        ("x~y", r"x\textasciitilde{}y"),
        ("x^y", r"x\textasciicircum{}y"),
        (r"x\path", r"x\textbackslash{}path"),
        ("[literal] café", "[literal] café"),
    ],
)
def test_bibtex_plain_title_is_escaped_once(text, escaped):
    # Arrange
    paper = {"title": text, "cite_key": "ownedfixture", "authors_str": "A. Researcher"}
    # Act
    first = to_bibtex(paper)
    second = to_bibtex({**paper, "title": escaped})
    # Assert -- already emitted safe escapes remain stable on reuse.
    assert ("  title = {" + escaped + "}," in first, second == first) == (True, True)


def test_bibtex_escapes_each_plain_text_field_and_keeps_identifiers_urls():
    # Arrange
    url = "https://example.invalid/a_b?q=1&x=2#fragment"
    doi = "10.5555/owned_fixture"
    paper = {
        "title": "A & B",
        "cite_key": "owned:fixture",
        "authors_str": "A&B Lab",
        "journal": "Computing in Science & Engineering",
        "volume": "x_1",
        "number": "#2",
        "pages": "50%",
        "year": 2020,
        "doi": doi,
        "url": url,
        "arxiv_id": "1234.5678v1",
    }
    # Act
    bib = to_bibtex(paper)
    # Assert
    assert all(
        line in bib
        for line in [
            "@article{owned:fixture,",
            r"author = {A\&B Lab}",
            r"journal = {Computing in Science \& Engineering}",
            r"volume = {x\_1}",
            r"number = {\#2}",
            r"pages = {50\%}",
            "year = {2020}",
            "doi = {" + doi + "}",
            "url = {" + url + "}",
            "eprint = {1234.5678v1}",
        ]
    )


def test_long_abstract_is_limited_before_escaping_without_cutting_commands():
    # Arrange
    paper = {"title": "Owned fixture", "abstract": "A&" * 260, "cite_key": "fixture"}
    # Act
    bib = to_bibtex(paper)
    # Assert
    assert "abstract = {" + (r"A\&" * 250) + "...}" in bib


def test_non_tex_export_keeps_plain_text_unchanged():
    # Arrange
    paper = {"title": "A & B_{literal}", "journal": "C & D", "year": 2020}
    # Act
    ris = to_ris(paper)
    # Assert -- BibTeX escaping must not leak into other formats.
    assert ("TI  - A & B_literal" in ris, "JO  - C & D" in ris, r"\&" in ris) == (
        True,
        True,
        False,
    )
