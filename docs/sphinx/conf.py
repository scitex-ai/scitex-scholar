"""Sphinx configuration for scitex-scholar documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------

project = "SciTeX Scholar"
copyright = "2026, Yusuke Watanabe"
author = "Yusuke Watanabe"

try:
    from importlib.metadata import version as _get_version

    release = _get_version("scitex-scholar")
except Exception:
    release = "0.0.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx_rtd_theme",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Mock optional / heavy deps so autodoc never fails on missing imports.
autodoc_mock_imports = ['mcp', 'playwright', 'aiohttp', 'pymupdf', 'fitz', 'bs4', 'beautifulsoup4', 'bibtexparser', 'feedparser', 'httpx', 'nest_asyncio', 'pandas', 'pydantic', 'yaml', 'requests', 'sql_manager', 'sqlalchemy', 'tenacity', 'tqdm', 'scitex', 'scitex_io', 'scitex_browser', 'scitex_logging']

autosummary_generate = True

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "to_claude/**"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"

html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "prev_next_buttons_location": "bottom",
}

html_static_path = ["_static"]
html_title = f"{project} v{release}"
html_short_title = project

html_context = {
    "display_github": True,
    "github_user": "scitex-ai",
    "github_repo": "scitex-scholar",
    "github_version": "develop",
    "conf_py_path": "/docs/sphinx/",
}

myst_enable_extensions = [
    "dollarmath",
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}
