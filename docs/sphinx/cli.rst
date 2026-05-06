CLI Reference
=============

The ``scitex-scholar`` command provides a noun-verb subcommand interface. Every
group has ``--help``:

.. code-block:: bash

   scitex-scholar --help
   scitex-scholar paper --help
   scitex-scholar library --help

Top-level groups
----------------

paper
~~~~~

Operate on a paper / batch of papers.

.. code-block:: bash

   # Single paper from DOI or title (was: ``single``)
   scitex-scholar paper process --doi "10.1093/brain/awx173" --project my_project
   scitex-scholar paper process --title "Seizure prediction with iEEG" --project my_project

   # Multiple papers in parallel (was: ``parallel``)
   scitex-scholar paper batch --dois 10.1/x 10.2/y --project my_project --num-workers 4

bibtex
~~~~~~

Operate on a BibTeX file.

.. code-block:: bash

   # Process every entry (was: top-level ``bibtex --bibtex …``)
   scitex-scholar bibtex process --bibtex refs.bib --project my_project \
                                 --num-workers 4 --browser-mode stealth

mcp
~~~

MCP server commands (Model Context Protocol).

.. code-block:: bash

   scitex-scholar mcp start          # start stdio server
   scitex-scholar mcp list-tools     # print scholar_* tool names
   scitex-scholar mcp doctor         # check fastmcp + handler imports
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

Library-tree management.

.. code-block:: bash

   # Symlink <project>/.scitex/scholar/library → ~/.scitex/scholar/library/
   scitex-scholar library link-project-tree .

   # Replace a library-symlink with a bib-filtered real directory
   scitex-scholar library materialize <link_path> --bib refs.bib

   # Replace a materialized directory with a symlink to ~/.scitex/scholar/library
   scitex-scholar library dematerialize <path>

   # Library SQLite index
   scitex-scholar library db build
   scitex-scholar library db migrate
   scitex-scholar library db lookup --doi 10.1/x
   scitex-scholar library db list --limit 20
   scitex-scholar library db dedupe --apply
   scitex-scholar library db audit

Migration from pre-1.3.0
------------------------

The pre-1.3.0 top-level commands (``single``, ``parallel``, top-level
``bibtex --bibtex``, ``highlight``, ``link-project-tree``, ``materialize``,
``dematerialize``, ``db``) still work but emit a one-line ``DeprecationWarning``
on stderr and will be **removed in 1.4.0**. See the project ``CHANGELOG.md`` for
the full migration table.
