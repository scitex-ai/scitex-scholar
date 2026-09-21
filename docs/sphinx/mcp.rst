MCP Server
==========

SciTeX Scholar ships scholar-specific MCP tools that register into the unified
``scitex serve`` server. An AI agent with MCP access can search papers, enrich BibTeX,
download PDFs, and overlay semantic highlights — all autonomously.

Installation
------------

.. code-block:: bash

   pip install scitex-scholar[all]

Starting the Server
-------------------

Use the unified scitex server (recommended):

.. code-block:: bash

   scitex serve                                # stdio (Claude Desktop, Cursor)
   scitex serve -t sse --port 8085             # SSE (remote via SSH)
   scitex serve -t http --port 8085            # HTTP (streamable)

The deprecated standalone server still works:

.. code-block:: bash

   scitex-scholar mcp

MCP Client Configuration
------------------------

Add to your MCP client configuration (e.g., Claude Desktop, Cursor):

.. code-block:: json

   {
     "mcpServers": {
       "scitex": {
         "command": "scitex",
         "args": ["serve"]
       }
     }
   }

Available Scholar Tools
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - tool
     - purpose
   * - ``scholar_search_papers``
     - Search local library or external sources (CrossRef, Semantic Scholar, PubMed, arXiv, OpenAlex).
   * - ``scholar_resolve_dois``
     - Resolve DOIs from titles (resumable for large batches).
   * - ``scholar_enrich_bibtex``
     - Enrich a BibTeX file with abstracts, citation counts, and impact factors.
   * - ``scholar_download_pdf``
     - Download a single PDF via OpenURL + publisher.
   * - ``scholar_download_pdfs_batch``
     - Batch PDF download with resume and concurrency control.
   * - ``scholar_get_library_status``
     - Report counts, last-modified times, missing PDFs in a project.
   * - ``scholar_parse_bibtex``
     - Parse a BibTeX file into structured paper records.
   * - ``scholar_validate_pdfs``
     - Validate downloaded PDFs for integrity and relevance.
   * - ``scholar_resolve_openurls``
     - Resolve institutional OpenURL links for a batch of DOIs.
   * - ``scholar_authenticate``
     - Start the interactive authentication flow (OpenAthens, etc.).
   * - ``scholar_check_auth_status``
     - Check whether a valid authenticated session exists.
   * - ``scholar_logout``
     - Clear authentication state.
   * - ``scholar_create_project``
     - Create a project in the scholar library.
   * - ``scholar_list_projects``
     - List all projects in the library.
   * - ``scholar_add_papers_to_project``
     - Attach existing papers to a project.
   * - ``scholar_export_papers``
     - Export a project to BibTeX, RIS, or other formats.
   * - ``scholar_parse_pdf_content``
     - Extract structured text content from a PDF.
   * - ``scholar_highlight_pdf``
     - **Overlay semantic highlights on a PDF** (claim / method / limitation /
       supportive / contradictive). See :doc:`semantic_highlight`.

Handler Integration
-------------------

Every handler is importable directly so any MCP server can register it:

.. code-block:: python

   from scitex_scholar._mcp.all_handlers import (
       search_papers_handler,
       resolve_dois_handler,
       enrich_bibtex_handler,
       download_pdfs_batch_handler,
       highlight_pdf_handler,
       # ... and the rest
   )
