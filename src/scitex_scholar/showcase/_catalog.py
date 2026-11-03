"""Bundled, source-verified example references; no user discovery or network."""

import copy
import hashlib
import json
from importlib.resources import files


def catalog():
    return json.loads(files(__package__).joinpath("mnist.json").read_text())


def mnist_references():
    """Return the curated MNIST reference metadata and primary-source URLs.

    Returns
    -------
    list of dict
        Actual bibliographic metadata, with no invented abstracts, citation
        counts, downloaded full texts, or scientific verification claims.
    """
    return copy.deepcopy(catalog()["references"])


def mnist_reference_bibtex():
    """Export the same curated references through Scholar's BibTeX formatter.

    Returns
    -------
    str
        BibTeX content only. This does not edit a project's bibliography.
    """
    from scitex_scholar.formatting import to_bibtex

    entries = []
    for ref in mnist_references():
        row = {**ref, "authors_str": " and ".join(ref["authors"])}
        row.update(cite_key=ref["key"], number=ref["issue"], url=ref["sources"][0])
        entries.append(to_bibtex(row))
    return "\n\n".join(entries) + "\n"


def identifier(ref):
    key = ref.get("doi") or ref["title"]
    return hashlib.sha1(key.encode()).hexdigest()[:8].upper()


def identity(metadata):
    doi = (metadata.get("id", {}).get("doi") or "").strip().casefold()
    title = " ".join((metadata.get("basic", {}).get("title") or "").split()).casefold()
    return ("doi", doi) if doi else ("title", title)


def paper_payload(ref, paper_id, project):
    source = ["curated-mnist-showcase-v1"]
    return {
        "metadata": {
            "id": {
                "doi": ref.get("doi"),
                "arxiv_id": ref.get("arxiv_id"),
                "doi_engines": source if ref.get("doi") else [],
                "arxiv_id_engines": source if ref.get("arxiv_id") else [],
            },
            "basic": {
                "title": ref["title"],
                "authors": ref["authors"],
                "year": ref["year"],
                "title_engines": source,
                "authors_engines": source,
                "year_engines": source,
                "type": "article",
            },
            "publication": {
                "journal": ref["journal"],
                "volume": ref["volume"],
                "issue": ref["issue"],
                "pages": ref["pages"],
            },
            "url": {
                "publisher": ref["sources"][0],
                "doi": "https://doi.org/" + ref["doi"] if ref.get("doi") else None,
            },
        },
        "container": {
            "library_id": paper_id,
            "projects": [project],
            "created_by": "scitex-example-mnist-v1",
        },
    }
