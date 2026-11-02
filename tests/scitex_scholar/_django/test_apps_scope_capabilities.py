"""The leaf's declared project/user capability contract needs its real SDK API."""

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

import scitex_scholar._django as module
from scitex_scholar._django.apps import ScholarEditorConfig


def test_app_config_exposes_both_declared_scope_capabilities():
    # Arrange — the real public SDK base resolves the real leaf manifest.
    config = ScholarEditorConfig("scitex_scholar._django", module)
    # Act
    capabilities = config.scope_capabilities
    # Assert
    assert capabilities == {"user": True, "project": True}


@pytest.mark.parametrize("extra", ["all", "dev"])
def test_sdk_requirement_excludes_versions_without_scope_contract(extra):
    # Arrange — official 0.3.11/0.3.16 wheels lack this public SDK property.
    path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    metadata = tomllib.loads(path.read_text())
    requirements = [Requirement(raw) for raw in metadata["project"]["optional-dependencies"][extra]]
    requirement = next(item for item in requirements if item.name == "scitex-sdk")
    # Act
    accepted = [requirement.specifier.contains(version) for version in ("0.3.11", "0.3.16")]
    # Assert
    assert accepted == [False, False]
