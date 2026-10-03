"""Offline stream and severity controls for the legacy Scholar consumers."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import scitex_scholar


def _run(tmp_path, code, level="info", after_import=""):
    home = tmp_path / "home"
    home.mkdir()
    # The release SIF layers declared dependencies on PYTHONPATH. Keep that
    # genuine caller target visible alongside the owning Scholar source.
    source_root = str(Path(scitex_scholar.__file__).resolve().parents[1])
    dependency_paths = [
        path for path in os.environ.get("PYTHONPATH", "").split(os.pathsep) if path
    ]
    env = {
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "HOME": str(home),
        "TMPDIR": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PYTHONPATH": os.pathsep.join(dict.fromkeys([source_root, *dependency_paths])),
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_COLOR": "1",
    }
    script = (
        "import sys\n"
        "def guard(event, args):\n"
        "    if event in {'socket.bind', 'socket.connect', 'socket.getaddrinfo'}:\n"
        "        raise RuntimeError('logging controls must remain offline')\n"
        "sys.addaudithook(guard)\n"
        "import scitex_logging as logging\n"
        f"logging.configure(level={level!r}, enable_file=False, capture_prints=False)\n"
        + after_import
        + "\n"
        + code
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result


@pytest.mark.parametrize("level", ["info", "critical"])
def test_requested_downloader_info_is_plain_at_every_threshold(tmp_path, level):
    # Arrange
    code = "from scitex_scholar.cli import download_pdf\nsys.argv=['download', 'info']\nassert download_pdf.main()==0"
    # Act
    result = _run(tmp_path, code, level)
    # Assert
    assert all(
        (
            result.stdout.count("Strategy: Institutional Authentication") == 1,
            "Zotero Translators: Enabled" in result.stdout,
            "INFO:" not in result.stdout,
            result.stderr == "",
        )
    ), result.stderr


@pytest.mark.parametrize("level", ["info", "critical"])
def test_missing_bibtex_keeps_failure_status_and_diagnostic_stream(tmp_path, level):
    # Arrange
    code = "from scitex_scholar.cli import download_pdf\nsys.argv=['download', 'bibtex', 'nonexistent-control.bib']\nassert download_pdf.main()==1"
    # Act
    result = _run(tmp_path, code, level)
    # Assert
    assert all(
        (
            result.stdout == "",
            all(
                (
                    result.stderr.count(
                        "BibTeX file not found: nonexistent-control.bib"
                    )
                    == 1,
                )
            )
            if level == "info"
            else all((result.stderr == "",)),
        )
    ), result.stderr


@pytest.mark.parametrize("level", ["info", "critical"])
def test_download_counts_are_results_even_when_failures_are_present(tmp_path, level):
    # Arrange
    code = "from scitex_scholar.cli.download_pdf import _print_download_summary\n_print_download_summary({'downloaded':2,'failed':1,'errors':['owned-control']})"
    # Act
    result = _run(tmp_path, code, level)
    # Assert
    assert all(
        (
            result.stdout
            == "\n✅ Downloaded: 2 PDFs\n❌ Failed: 1\n⚠️  Errors: ['owned-control']\n",
            result.stderr == "",
        )
    ), result.stderr


@pytest.mark.parametrize("level", ["info", "critical"])
def test_browser_diagnostics_follow_configured_level_after_import(tmp_path, level):
    # Arrange
    code = "chrome.logger.info('browser-control')"
    # Act
    result = _run(
        tmp_path,
        code,
        level,
        f"from scitex_scholar.cli import chrome\nlogging.configure(level={level!r},enable_file=False,capture_prints=True)",
    )
    # Assert
    assert all(
        (
            result.stdout == "",
            result.stderr == ("INFO: browser-control\n" if level == "info" else ""),
        )
    ), result.stderr


def test_monitor_without_ui_preserves_error_severity_and_suppresses_info(tmp_path):
    # Arrange
    code = "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor\nmonitor=DownloadMonitor({},None,None)\nmonitor._say('hidden-info','info')\nmonitor._say('visible-error','error')"
    # Act
    result = _run(tmp_path, code, "fail")
    # Assert
    assert all(
        (
            result.stdout == "",
            "hidden-info" not in result.stderr,
            result.stderr == "FAIL: visible-error\n",
        )
    ), result.stderr


def test_monitor_error_uses_existing_ui_fail_level_below_error_threshold(tmp_path):
    # Arrange
    code = "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor,TerminalUI\nDownloadMonitor({},None,None)._say('fallback-error','error')\nDownloadMonitor({},None,None,ui=TerminalUI())._say('ui-error','error')"
    # Act
    result = _run(tmp_path, code, "error")
    # Assert
    assert all((result.stdout == result.stderr == "",)), result.stderr


def test_monitor_warning_has_same_stream_and_level_with_or_without_ui(tmp_path):
    # Arrange
    code = "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor,TerminalUI\nDownloadMonitor({},None,None)._say('fallback-warning','warn')\nDownloadMonitor({},None,None,ui=TerminalUI())._say('ui-warning','warn')"
    # Act
    result = _run(tmp_path, code, "warning")
    # Assert
    assert all(
        (
            result.stdout == "",
            result.stderr == "WARN: fallback-warning\nWARN: ui-warning\n",
        )
    ), result.stderr


def test_monitor_critical_threshold_suppresses_fallback_info(tmp_path):
    # Arrange
    code = "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor\nDownloadMonitor({},None,None)._say('hidden-info','info')"
    # Act
    result = _run(tmp_path, code, "critical")
    # Assert
    assert all((result.stdout == result.stderr == "",)), result.stderr


@pytest.mark.parametrize("level", ["info", "critical"])
def test_project_status_counts_remain_a_complete_plain_report(tmp_path, level):
    # Arrange
    code = "from scitex_scholar.cli.handlers.project_handler import _print_project_summary\n_print_project_summary('synthetic',4,{'PDF-3s':1,'PDF-2f':1,'PDF-0p':1,'PDF-1r':1})"
    # Act
    result = _run(tmp_path, code, level)
    # Assert
    assert all(
        (
            result.stdout
            == "\nProject: synthetic\nPapers: 4\n\nPDF Status:\n  ✓ Downloaded (PDF-3s): 1\n  ✗ Failed (PDF-2f):     1\n  ⧗ Pending (PDF-0p):    1\n  ⟳ Running (PDF-1r):    1\n\nCoverage: 1/4 (25.0%)\n\n",
            result.stderr == "",
        )
    ), result.stderr


def test_empty_project_summary_does_not_divide_by_zero(tmp_path):
    # Arrange
    code = "from scitex_scholar.cli.handlers.project_handler import _print_project_summary\n_print_project_summary('empty',0,{'PDF-3s':0,'PDF-2f':0,'PDF-0p':0,'PDF-1r':0})"
    # Act
    result = _run(tmp_path, code, "critical")
    # Assert
    assert all(
        (
            "Papers: 0" in result.stdout,
            "Coverage:" not in result.stdout,
            result.stderr == "",
        )
    ), result.stderr


@pytest.mark.parametrize("level", ["info", "critical"])
def test_scholar_banner_obeys_level_changes_without_duplicate_handlers(tmp_path, level):
    # Arrange
    code = f"logging.configure(level='critical',enable_file=False,capture_prints=True)\nserver._print_banner('127.0.0.1',31297)\nlogging.configure(level={level!r},enable_file=False,capture_prints=True)\nserver._print_banner('127.0.0.1',31297)\nserver._print_banner('127.0.0.1',31297)"
    # Act
    result = _run(
        tmp_path, code, level, "from scitex_scholar._django import _server as server"
    )
    # Assert
    assert all(
        (
            result.stderr == "",
            all(
                (
                    result.stdout.count("SciTeX Scholar GUI: http://127.0.0.1:31297")
                    == 2,
                    result.stdout.count("Press Ctrl+C to stop") == 2,
                )
            )
            if level == "info"
            else all((result.stdout == "",)),
        )
    ), result.stderr
