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
    env = {
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        "HOME": str(home),
        "TMPDIR": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PYTHONPATH": str(Path(scitex_scholar.__file__).resolve().parents[1]),
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
    result = _run(
        tmp_path,
        "from scitex_scholar.cli import download_pdf\n"
        "sys.argv=['download', 'info']\nassert download_pdf.main()==0",
        level,
    )
    assert result.stdout.count("Strategy: Institutional Authentication") == 1
    assert "Zotero Translators: Enabled" in result.stdout
    assert "INFO:" not in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_missing_bibtex_keeps_failure_status_and_diagnostic_stream(tmp_path, level):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli import download_pdf\n"
        "sys.argv=['download', 'bibtex', 'nonexistent-control.bib']\n"
        "assert download_pdf.main()==1",
        level,
    )
    assert result.stdout == ""
    if level == "info":
        assert (
            result.stderr.count("BibTeX file not found: nonexistent-control.bib") == 1
        )
    else:
        assert result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_download_counts_are_results_even_when_failures_are_present(tmp_path, level):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.download_pdf import _print_download_summary\n"
        "_print_download_summary({'downloaded':2,'failed':1,'errors':['owned-control']})",
        level,
    )
    assert result.stdout == (
        "\n✅ Downloaded: 2 PDFs\n❌ Failed: 1\n⚠️  Errors: ['owned-control']\n"
    )
    assert result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_browser_diagnostics_follow_configured_level_after_import(tmp_path, level):
    result = _run(
        tmp_path,
        "chrome.logger.info('browser-control')",
        level,
        "from scitex_scholar.cli import chrome\n"
        f"logging.configure(level={level!r},enable_file=False,capture_prints=True)",
    )
    assert result.stdout == ""
    assert result.stderr == ("INFO: browser-control\n" if level == "info" else "")


def test_monitor_without_ui_preserves_error_severity_and_suppresses_info(tmp_path):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor\n"
        "monitor=DownloadMonitor({},None,None)\n"
        "monitor._say('hidden-info','info')\n"
        "monitor._say('visible-error','error')",
        "fail",
    )
    assert result.stdout == ""
    assert "hidden-info" not in result.stderr
    assert result.stderr == "FAIL: visible-error\n"


def test_monitor_error_uses_existing_ui_fail_level_below_error_threshold(tmp_path):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor,TerminalUI\n"
        "DownloadMonitor({},None,None)._say('fallback-error','error')\n"
        "DownloadMonitor({},None,None,ui=TerminalUI())._say('ui-error','error')",
        "error",
    )
    assert result.stdout == result.stderr == ""


def test_monitor_warning_has_same_stream_and_level_with_or_without_ui(tmp_path):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor,TerminalUI\n"
        "DownloadMonitor({},None,None)._say('fallback-warning','warn')\n"
        "DownloadMonitor({},None,None,ui=TerminalUI())._say('ui-warning','warn')",
        "warning",
    )
    assert result.stdout == ""
    assert result.stderr == "WARN: fallback-warning\nWARN: ui-warning\n"


def test_monitor_critical_threshold_suppresses_fallback_info(tmp_path):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.open_browser_monitored import DownloadMonitor\n"
        "DownloadMonitor({},None,None)._say('hidden-info','info')",
        "critical",
    )
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_project_status_counts_remain_a_complete_plain_report(tmp_path, level):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.handlers.project_handler import _print_project_summary\n"
        "_print_project_summary('synthetic',4,"
        "{'PDF-3s':1,'PDF-2f':1,'PDF-0p':1,'PDF-1r':1})",
        level,
    )
    assert result.stdout == (
        "\nProject: synthetic\nPapers: 4\n\nPDF Status:\n"
        "  ✓ Downloaded (PDF-3s): 1\n  ✗ Failed (PDF-2f):     1\n"
        "  ⧗ Pending (PDF-0p):    1\n  ⟳ Running (PDF-1r):    1\n"
        "\nCoverage: 1/4 (25.0%)\n\n"
    )
    assert result.stderr == ""


def test_empty_project_summary_does_not_divide_by_zero(tmp_path):
    result = _run(
        tmp_path,
        "from scitex_scholar.cli.handlers.project_handler import _print_project_summary\n"
        "_print_project_summary('empty',0,"
        "{'PDF-3s':0,'PDF-2f':0,'PDF-0p':0,'PDF-1r':0})",
        "critical",
    )
    assert "Papers: 0" in result.stdout
    assert "Coverage:" not in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("level", ["info", "critical"])
def test_scholar_banner_obeys_level_changes_without_duplicate_handlers(tmp_path, level):
    result = _run(
        tmp_path,
        "logging.configure(level='critical',enable_file=False,capture_prints=True)\n"
        "server._print_banner('127.0.0.1',31297)\n"
        f"logging.configure(level={level!r},enable_file=False,capture_prints=True)\n"
        "server._print_banner('127.0.0.1',31297)\n"
        "server._print_banner('127.0.0.1',31297)",
        level,
        "from scitex_scholar._django import _server as server",
    )
    assert result.stderr == ""
    if level == "info":
        assert result.stdout.count("SciTeX Scholar GUI: http://127.0.0.1:31297") == 2
        assert result.stdout.count("Press Ctrl+C to stop") == 2
    else:
        assert result.stdout == ""
