"""Real Hatch artifacts carry the SDK-produced inert declaration through sdist."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder
from scitex_sdk.app.api_build import build_inert_api_metadata
from scitex_sdk.app.api_mount import parse_inert_descriptor

ROOT = Path(__file__).resolve().parents[2]


def test_wheel_metadata_matches_shared_source_producer(tmp_path):
    # Arrange
    expected = build_inert_api_metadata(ROOT)
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    # Act
    artifact = next(
        WheelBuilder(str(ROOT)).build(directory=str(wheel_dir), versions=["standard"])
    )
    with zipfile.ZipFile(artifact) as wheel:
        paths = [
            name
            for name in wheel.namelist()
            if name.endswith(".dist-info/scitex_api.json")
        ]
        actual = wheel.read(paths[0]) if len(paths) == 1 else b""
    # Assert
    assert (len(paths), actual) == (1, expected)


def test_sdist_rebuilt_wheel_keeps_hook_descriptor_and_owned_handler(tmp_path):
    # Arrange
    sdist_dir = tmp_path / "sdist"
    sdist_dir.mkdir()
    artifact = next(SdistBuilder(str(ROOT)).build(directory=str(sdist_dir)))
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    # Act
    with tarfile.open(artifact) as sdist:
        sdist.extractall(unpacked, filter="data")
    source = next(unpacked.iterdir())
    wheel_dir = tmp_path / "rebuilt-wheel"
    wheel_dir.mkdir()
    rebuilt = next(
        WheelBuilder(str(source)).build(directory=str(wheel_dir), versions=["standard"])
    )
    with zipfile.ZipFile(rebuilt) as wheel:
        descriptor = next(
            name
            for name in wheel.namelist()
            if name.endswith(".dist-info/scitex_api.json")
        )
        plugin = parse_inert_descriptor(wheel.read(descriptor).decode("utf-8"))
        owned_modules = {
            name
            for name in wheel.namelist()
            if name in {"scitex_scholar/_web/_api.py", "scitex_scholar/_web/_views.py"}
        }
    # Assert
    assert (
        (source / "scripts/hatch_build.py").is_file(),
        plugin.id,
        plugin.routes[0].handler,
        owned_modules,
    ) == (
        True,
        "scitex-scholar",
        "scitex_scholar._web._views:search_syntax_help",
        {"scitex_scholar/_web/_api.py", "scitex_scholar/_web/_views.py"},
    )
