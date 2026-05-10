CLI Reference
=============

The ``scitex-scholar`` command provides a Click-based noun-verb subcommand
interface. Every group has ``--help``; pass ``--help-recursive`` at the top
level for a full overview, ``--version``/``-V`` for the installed version, and
``--json`` (where supported) for machine-readable output.

.. code-block:: bash

   scitex-scholar --help
   scitex-scholar --help-recursive
   scitex-scholar --version
   scitex-scholar paper --help
   scitex-scholar library --help

Top-level groups
----------------

paper
~~~~~

Operate on a paper / batch of papers.

.. code-block:: bash

   # Single paper from DOI or title
   scitex-scholar paper fetch --doi "10.1093/brain/awx173" --project my_project
   scitex-scholar paper fetch --title "Seizure prediction with iEEG" --project my_project

   # ``--doi`` accepts URL form too: ``https://doi.org/...``,
   # ``http://dx.doi.org/...``, or ``doi:10.x/y``.

   # Multiple papers in parallel
   scitex-scholar paper fetch-batch --dois 10.1/x --dois 10.2/y \
                                    --project my_project --num-workers 4

Local-PDF import (skips the browser/download stack):

.. code-block:: bash

   # Main PDF only — metadata enrichment still runs from --doi/--title
   scitex-scholar paper fetch --doi 10.1002/epi.70076 \
                              --pdf-main ~/Downloads/Liu_2026.pdf \
                              --project neurovista

   # With supplementary files and attachments (both flags repeatable)
   scitex-scholar paper fetch --doi 10.1038/s41467-020-15908-3 \
                              --pdf-main ~/Downloads/main.pdf \
                              --pdf-supple ~/Downloads/MOESM1_ESM.pdf \
                              --pdf-supple ~/Downloads/MOESM2_ESM.pdf \
                              --attachment ~/Downloads/dataset.csv \
                              --project neurovista

Storage convention: ``--pdf-main`` is placed at
``MASTER/<id>/<First>-<Year>-<Journal>.pdf`` (chmod 444 — Zotero-style
immutable canonical record). Supplementary files land as
``supple-<original_name>`` and attachments as
``additional-<original_name>``. Each file is recorded with role + SHA-256
in ``metadata.path.files`` so ``library audit-files`` can verify integrity.

Mutating verbs accept ``--dry-run`` and ``-y/--yes``.

bibtex
~~~~~~

Operate on a BibTeX file.

.. code-block:: bash

   # Process every entry (was: top-level ``bibtex --bibtex …``)
   scitex-scholar bibtex import --bibtex refs.bib --project my_project \
                                --num-workers 4 --browser-mode stealth

mcp
~~~

MCP server commands (Model Context Protocol).

.. code-block:: bash

   scitex-scholar mcp start                  # start stdio server
   scitex-scholar mcp start --dry-run        # print plan, exit
   scitex-scholar mcp list-tools             # print scholar_* tool names
   scitex-scholar mcp list-tools --json      # machine-readable
   scitex-scholar mcp doctor                 # check fastmcp + handler imports
   scitex-scholar mcp install --claude-code  # config snippet

Prefer the unified ``scitex serve`` server when integrating with the rest of
the SciTeX ecosystem.

pdf
~~~

PDF post-processing. See :doc:`semantic_highlight`.

.. code-block:: bash

   export ANTHROPIC_API_KEY=sk-ant-...

   scitex-scholar pdf highlight paper.pdf
   scitex-scholar pdf highlight paper.pdf -o out.pdf
   scitex-scholar pdf highlight paper.pdf --model claude-sonnet-4-6
   scitex-scholar pdf highlight paper.pdf --stub
   scitex-scholar pdf highlight paper.pdf --dry-run
   scitex-scholar pdf highlight paper.pdf --max-blocks 20

   # Offline label-apply workflow
   scitex-scholar pdf highlight paper.pdf --labels-dump blocks.json
   scitex-scholar pdf highlight paper.pdf --labels-apply labels.json

Also available as a standalone module:

.. code-block:: bash

   python -m scitex_scholar.pdf_highlight paper.pdf

library
~~~~~~~

Library-tree management. ``--help`` is **categorized** into four groups:
``Daily`` (the common workflow), ``Layout`` (where the data lives),
``Share`` (move it elsewhere), and ``Database`` (integrity / index).

Daily
'''''

.. code-block:: bash

   # All projects: counts only. Add ``-v`` / ``-vv`` / ``-vvv`` for detail.
   scitex-scholar library list

   # Single project: per-paper detail by default (auto-verbose).
   scitex-scholar library list neurovista

   # Open every paper-URL in a browser. ``--watch`` auto-imports any PDF
   # downloaded during the session (Playwright + watchdog dual-watch).
   scitex-scholar library open-urls neurovista --watch

   # One-button maintenance: reconcile container.projects ↔ symlinks,
   # regenerate readable names (PDF-NN_CC-..._IF-..._...). Optionally
   # rsync after; --sync HOST is repeatable.
   scitex-scholar library refresh
   scitex-scholar library refresh neurovista
   scitex-scholar library refresh neurovista --sync spartan
   scitex-scholar library refresh neurovista --sync spartan --sync nas

Layout
''''''

.. code-block:: bash

   # Add a project-local view of the home library via one symlink:
   #   <PROJECT-DIR>/.scitex/scholar/library/<project> -> ~/.scitex/scholar/library/<project>
   # No data is moved; --unbind removes the symlink.
   scitex-scholar library bind neurovista ~/proj/neurovista
   scitex-scholar library bind neurovista ~/proj/neurovista --unbind

   # Verbless shorthand (only when <project> already exists in home).
   scitex-scholar library neurovista ~/proj/neurovista

   # Whole-library view symlink (older pattern).
   scitex-scholar library link-project-tree .

   # Bib-filtered real directory ↔ view-symlink.
   scitex-scholar library materialize <link_path> --bib refs.bib
   scitex-scholar library dematerialize <path>

Share
'''''

.. code-block:: bash

   # rsync the library to/from a remote host. ``--remote-path`` overrides
   # the default (``.scitex/scholar/library/[<project>/]``).
   scitex-scholar library sync spartan --project neurovista
   scitex-scholar library sync spartan --project neurovista \
       --remote-path proj/neurovista/.scitex/scholar/library/neurovista
   scitex-scholar library sync spartan --pull --project neurovista

   # Portable export.
   scitex-scholar library export neurovista                  # tarball (default)
   scitex-scholar library export neurovista --format bibtex
   scitex-scholar library export neurovista --format flat-pdfs

   # Bidirectional Zotero migration (local SQLite, no API key).
   # Engine wired; verify on a real round-trip before relying on it.
   scitex-scholar library zotero import --project demo --collection demo
   scitex-scholar library zotero export --project demo
   scitex-scholar library zotero diff --project demo

Database / integrity
''''''''''''''''''''

.. code-block:: bash

   # SQLite index.
   scitex-scholar library db build --dry-run
   scitex-scholar library db build
   scitex-scholar library db migrate
   scitex-scholar library db lookup --doi 10.1/x --json
   scitex-scholar library db list --limit 20 --json
   scitex-scholar library db audit --json

   # File integrity: verify metadata.path.files against disk
   # (presence + SHA-256, role-aware).
   scitex-scholar library audit-files
   scitex-scholar library audit-files --project neurovista --json
   scitex-scholar library audit-files --no-rehash    # presence only (fast)

skills
~~~~~~

Bundled SciTeX-Scholar skill leaves (under
``src/scitex_scholar/_skills/scitex-scholar/``).

.. code-block:: bash

   scitex-scholar skills list
   scitex-scholar skills list --json
   scitex-scholar skills get 04_cli-reference
   scitex-scholar skills install            # symlink into ~/.claude/skills/
   scitex-scholar skills install --copy --force --dry-run

Python API introspection
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   scitex-scholar list-python-apis           # one name per line
   scitex-scholar list-python-apis -v        # with signatures
   scitex-scholar list-python-apis --json    # machine-readable

Migration from pre-1.3.0
------------------------

The pre-1.3.0 top-level commands (``single``, ``parallel``, top-level
``bibtex --bibtex``, ``highlight``, ``link-project-tree``, ``materialize``,
``dematerialize``, ``db``) still work but emit a one-line ``DeprecationWarning``
on stderr and will be **removed in 1.4.0**. See the project ``CHANGELOG.md`` for
the full migration table.
