"""Real stdlib child-process controls for the native release import boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / ".github/ci/probe-first-observer.py"


@pytest.fixture
def owned_boundary(tmp_path):
    root = tmp_path / "context"
    root.mkdir(mode=0o700)
    password = root / "empty-pgpass"
    password.touch(mode=0o600)
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": str(root),
        "PGPASSFILE": str(password),
        "SCITEX_STORE_DSN": f"postgresql://refuse@/refuse?host={root / 'unavailable-store'}",
    }
    environment["SCITEX_CARDS_DB"] = environment["SCITEX_STORE_DSN"]
    return root, environment


def run_probe(environment):
    return subprocess.run(
        [sys.executable, "-I", "-S", str(PROBE), "--early"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_first_observer_proves_owned_unavailable_route(owned_boundary):
    # Arrange
    _root, environment = owned_boundary
    # Act
    result = run_probe(environment)
    # Assert
    assert result.returncode == 0 and json.loads(result.stdout) == {
        "earliest_stdlib_observer": True,
        "explicit_unavailable_store": True,
        "inherited_pg_absent": True,
    }


@pytest.mark.parametrize(
    "name",
    ["PGSERVICE", "PGOPTIONS", "APPTAINERENV_PGHOST", "SINGULARITYENV_PGSERVICE"],
)
def test_first_observer_refuses_inherited_routing(owned_boundary, name):
    # Arrange
    _root, environment = owned_boundary
    environment[name] = "owned-hostile-routing-negative-control"
    # Act
    result = run_probe(environment)
    # Assert
    assert result.returncode != 0 and "Inherited PostgreSQL routing" in result.stderr


def test_first_observer_refuses_password_symlink(owned_boundary):
    # Arrange
    root, environment = owned_boundary
    password = Path(environment["PGPASSFILE"])
    password.unlink()
    target = root / "other-empty-file"
    target.touch(mode=0o600)
    password.symlink_to(target)
    # Act
    result = run_probe(environment)
    # Assert
    assert result.returncode != 0 and "password file" in result.stderr


def test_first_observer_refuses_group_writable_root(owned_boundary):
    # Arrange
    root, environment = owned_boundary
    root.chmod(0o770)
    # Act
    result = run_probe(environment)
    # Assert
    assert result.returncode != 0 and "exclusively owned" in result.stderr


def test_first_observer_refuses_network_store(owned_boundary):
    # Arrange
    _root, environment = owned_boundary
    environment["SCITEX_STORE_DSN"] = "postgresql://owned@127.0.0.1:1/unavailable"
    environment["SCITEX_CARDS_DB"] = environment["SCITEX_STORE_DSN"]
    # Act
    result = run_probe(environment)
    # Assert
    assert result.returncode != 0 and "explicit unavailable store" in result.stderr
