# `_bibtex/` — BibTeXHandler internals

Mixins composed by `storage/BibTeXHandler.py`, which stays a thin public class.
Split out of a single 1155-line module so each stage of the BibTeX lifecycle
owns one file and stays under the repo's 512-line file gate.

| Module | Mixin | Responsibility |
| --- | --- | --- |
| `_parsing.py` | `BibTeXParsingMixin` | BibTeX file/text → `Paper` objects |
| `_writing.py` | `BibTeXWritingMixin` | `Paper` objects → BibTeX entries and files |
| `_merging.py` | `BibTeXMergingMixin` | Merge many `.bib` files, dedupe and reconcile papers |
| `_projects.py` | `BibTeXProjectsMixin` | A project's `info/bibliography/` tree and exports |
| `_comments.py` | — | `sanitize_bibtex_comments()` |

## Why `_comments.py` exists

BibTeX parsers find entries by scanning for `@` and do **not** treat `%` as a
comment introducer. A raw `@` in a generated header comment — an email address,
a handle, an `@`-bearing source filename — is therefore read as the start of a
malformed entry and aborts the parse of an otherwise valid file.

`sanitize_bibtex_comments()` is the **single** place that neutralizes this. Every
writer that emits file content funnels its output through it, so a new header
line cannot reintroduce the bug. If you add a writer, route it through that
function rather than escaping `@` at the call site.

Note this package is separate from `storage/_mixins/`, which holds the mixins for
`LibraryManager`.
