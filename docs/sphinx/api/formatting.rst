scitex_scholar.formatting
=========================

.. automodule:: scitex_scholar.formatting
   :members:
   :undoc-members:
   :show-inheritance:

BibTeX plain text
-----------------

``to_bibtex`` escapes TeX special characters in plain title, author, journal,
volume, issue, page, year and abstract fields. Safe escapes emitted by the
encoder remain stable on reuse. Identifiers, URLs and citation keys are not
rewritten. Raw LaTeX commands in bibliographic text are literal text, not an
instruction to execute them. Other export formats retain their existing
plain-text handling. Abstract limits apply before escaping, so generated
escape commands are not cut in half.
