"""Verify the CI bootstrap fails closed and reaches every Python test leg."""

import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/ci/setup-node-owned.sh"


def test_required_matrix_uses_the_owned_node_preparation_port():
    # Arrange
    path = ROOT / ".github/workflows/pytest-matrix-on-ubuntu-py3-11-3-12-3-13.yml"
    job = yaml.safe_load(path.read_text())["jobs"]["pytest-matrix"]
    # Act
    actual = (job["with"]["pre_test_command"], "if" in job, "strategy" in job)
    # Assert: preparation is common to the reusable workflow's complete matrix.
    assert actual == ("bash .github/ci/setup-node-owned.sh", False, False)


def test_missing_job_scratch_refuses_before_any_download(tmp_path):
    # Arrange
    environment = os.environ.copy()
    environment.pop("RUNNER_TEMP", None)
    environment["GITHUB_PATH"] = str(tmp_path / "github-path")
    # Act
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Assert
    assert (
        result.returncode != 0,
        "RUNNER_TEMP" in result.stderr,
        (tmp_path / "github-path").exists(),
    ) == (True, True, False)


def test_corrupt_download_cannot_publish_an_ambient_runtime(tmp_path):
    # Arrange: substitute only the downloader, supplying genuinely corrupt bytes.
    tools = tmp_path / "tools"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = --output ]; then printf corrupt > "$2"; exit 0; fi\n'
        "  shift\ndone\nexit 1\n"
    )
    curl.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        PATH=str(tools) + os.pathsep + environment["PATH"],
        RUNNER_TEMP=str(tmp_path),
        GITHUB_JOB="owned-node-negative",
        GITHUB_RUN_ID="123",
        GITHUB_RUN_ATTEMPT="1",
        GITHUB_PATH=str(tmp_path / "github-path"),
    )
    # Act: real shell and sha256sum must reject the downloader's invalid body.
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Assert: no PATH binding means the next CI step cannot fall back to a mask.
    assert (result.returncode != 0, (tmp_path / "github-path").exists()) == (
        True,
        False,
    )
