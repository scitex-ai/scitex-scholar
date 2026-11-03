"""Scholar declares only the existing static help operation and its real shape."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scitex_scholar._web._api import plugin


def test_static_help_contract_has_no_search_inputs_or_project_claims():
    # Arrange
    route = plugin.routes[0]
    # Act
    observed = (
        plugin.id,
        route.path,
        tuple(route.methods),
        route.request,
        route.auth.public,
        route.auth.project_scope,
        route.audit.level,
        route.read_only,
        tuple(route.errors),
    )
    # Assert
    assert observed == (
        "scitex-scholar",
        "api/search/syntax-help",
        ("GET",),
        None,
        True,
        "none",
        "none",
        True,
        (),
    )


def test_response_contract_describes_actual_five_document_keys():
    # Arrange
    route = plugin.routes[0]
    # Act
    observed = {field.name: field.type for field in route.response.fields}
    # Assert
    assert observed == {
        "status": "string",
        "syntax": "object",
        "examples": "array",
        "available_sources": "array",
        "query_parameters": "object",
    }


def test_descriptor_import_and_render_do_not_import_http_or_search_consumers(tmp_path):
    # Arrange
    source = Path(__file__).resolve().parents[3] / "src"
    environment = {
        **os.environ,
        "PYTHONPATH": str(source),
        "SCITEX_DIR": str(tmp_path / "state"),
    }
    script = """import json,sys
from scitex_scholar._web._api import plugin
plugin.openapi_fragment()
print(json.dumps([name for name in sys.modules if name == 'django' or name.startswith('scitex_scholar._django') or name.startswith('scitex_scholar.search_engines')]))
"""
    # Act
    process = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    modules = json.loads(process.stdout) if process.returncode == 0 else process.stderr
    # Assert
    assert (process.returncode, modules) == (0, [])
