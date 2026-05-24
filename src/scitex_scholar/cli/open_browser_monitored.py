#!/usr/bin/env python3
"""Open browser with download monitoring and auto-linking.

This CLI tool opens a visible browser and monitors downloads, automatically
moving downloaded PDFs to the correct library location.

Usage:
    # Monitor downloads and auto-link
    python -m scitex_scholar.cli.open_browser_monitored --project neurovista

    # Monitor pending papers only
    python -m scitex_scholar.cli.open_browser_monitored --project neurovista --pending
"""

import argparse
import json
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scitex_logging import getLogger

from scitex_scholar.config import ScholarConfig

logger = getLogger(__name__)


class TerminalUI:
    """Breathing spinner with live counters; lock-serialized writes.

    Spawns a daemon thread that rewrites a single status line using ``\\r``
    and ANSI ``\\033[K`` (clear-to-EOL). Event messages are printed via
    :meth:`event` which clears the spinner line, prints the message with a
    newline, and lets the spinner thread redraw on its next tick. This keeps
    the spinner from clobbering log output and vice versa.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    # Levels for routing log lines to scitex-logging (colored).
    _LEVEL_FUNC = {
        "info": "info",
        "success": "success",
        "warn": "warning",
        "warning": "warning",
        "error": "fail",
        "debug": "debug",
    }

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._frame_idx = 0
        self.start_time = time.time()
        self.imported = 0
        self.unmatched = 0
        self.detected = 0
        self.watch_dir: Optional[Path] = None
        self._thread: Optional[threading.Thread] = None
        self._enabled = sys.stdout.isatty()
        self._debug_fp = None  # file handle for debug-only lines

    def start(self, watch_dir: Path) -> None:
        self.watch_dir = watch_dir
        if not self._enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        if self._enabled:
            with self.lock:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()

    def attach_debug_file(self, path: Path) -> None:
        try:
            self._debug_fp = open(path, "a", encoding="utf-8")
        except OSError:
            self._debug_fp = None

    def event(self, msg: str, level: str = "info") -> None:
        """Print to terminal via scitex-logging (colored), preserving spinner.

        Use level='debug' for noisy lines you want hidden from the terminal
        but kept in the debug log file (NAV/DEBUG/NEWTAB).
        """
        # Always record in the debug log if it's open.
        if self._debug_fp is not None:
            try:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._debug_fp.write(f"{ts} [{level}] {msg}\n")
                self._debug_fp.flush()
            except OSError:
                pass

        if level == "debug":
            return  # debug stays in file only — no terminal noise

        with self.lock:
            if self._enabled:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
            fn_name = self._LEVEL_FUNC.get(level, "info")
            log_fn = getattr(logger, fn_name, logger.info)
            try:
                log_fn(msg)
            except Exception:
                # Fallback if scitex-logging shape changes.
                sys.stderr.write(msg + "\n")

    def _run(self) -> None:
        while not self._stop.is_set():
            with self.lock:
                elapsed = int(time.time() - self.start_time)
                frame = self.FRAMES[self._frame_idx % len(self.FRAMES)]
                line = (
                    f"{frame} Watching {self.watch_dir}  "
                    f"detected={self.detected}  "
                    f"imported={self.imported}  unmatched={self.unmatched}  "
                    f"elapsed={elapsed}s"
                )
                sys.stdout.write("\r" + line + "\033[K")
                sys.stdout.flush()
            self._frame_idx += 1
            self._stop.wait(0.1)


def _wait_for_stable_file(
    path: Path,
    *,
    stable_window_sec: float = 0.3,
    poll_sec: float = 0.1,
    timeout_sec: float = 30.0,
) -> bool:
    """Block until ``path``'s size is unchanged for ``stable_window_sec``.

    Returns True on stability, False on timeout or disappearance.
    """
    deadline = time.time() + timeout_sec
    last_size = -1
    last_change = time.time()
    while time.time() < deadline:
        if not path.exists():
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size != last_size:
            last_size = size
            last_change = time.time()
        elif time.time() - last_change >= stable_window_sec and size > 0:
            return True
        time.sleep(poll_sec)
    return False


class DownloadMonitor(FileSystemEventHandler):
    """Monitor downloads folder and link PDFs to library."""

    def __init__(
        self,
        paper_id_map: Dict[str, str],
        library_manager,
        config: ScholarConfig,
        unmatched_dir: Optional[Path] = None,
        ui: Optional["TerminalUI"] = None,
    ):
        """
        Args:
            paper_id_map: Maps download filenames to paper_ids
            library_manager: LibraryManager instance for organizing files
            config: Scholar configuration
            unmatched_dir: If set, unmatched PDFs created during the watch
                session are moved here instead of left in the watch dir.
            ui: Optional :class:`TerminalUI` for online feedback.
        """
        self.name = self.__class__.__name__
        self.paper_id_map = paper_id_map
        self.library_manager = library_manager
        self.config = config
        self.processed_files = set()
        self.unmatched_dir = Path(unmatched_dir) if unmatched_dir else None
        self.ui = ui
        # Filename → paper_id seeded by Playwright's `page.on("download")`.
        # When a download originates from a tab we opened for a known
        # paper, the mapping lets us skip content matching entirely.
        self.pending_downloads: Dict[str, str] = {}
        # paper_id -> bibliographic dict (first_author/year/journal/...)
        # for human-readable log labels.
        self.id_to_meta: Dict[str, dict] = {}

    def _label_for(self, paper_id: str) -> str:
        meta = self.id_to_meta.get(paper_id)
        return _label(meta) if meta else paper_id

    def _say(self, msg: str, level: str = "info") -> None:
        if self.ui is not None:
            self.ui.event(msg, level=level)
        else:
            print(msg, flush=True)

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_pdf(Path(event.src_path), "created")

    def on_moved(self, event):
        # Chrome finalizes downloads as `<name>.pdf.crdownload` -> `<name>.pdf`,
        # which fires `on_moved`, not `on_created`. Firefox/Safari behave
        # similarly with `.part`/`.download` temp suffixes.
        if event.is_directory:
            return
        self._handle_pdf(Path(event.dest_path), "moved")

    def on_modified(self, event):
        # Some browsers rewrite the existing file in place — pick up the final
        # PDF on the last write event.
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".pdf":
            self._handle_pdf(path, "modified")

    def _handle_pdf(self, file_path: Path, source_event: str):
        """Process a PDF file regardless of which watchdog event surfaced it."""
        if file_path.suffix.lower() != ".pdf":
            return

        # Dedupe by basename — the same PDF lands in BOTH watch dirs
        # (Playwright dir + ~/Downloads), firing watchdog twice.
        if file_path.name in self.processed_files:
            self._say(f"already processed: {file_path.name}", level="debug")
            return

        # 1) Immediate prominent feedback.
        self._say(f"DETECTED {file_path.name}", level="success")
        if self.ui is not None:
            self.ui.detected += 1

        # 2) Stability poll.
        if not _wait_for_stable_file(file_path):
            self._say(f"PDF never stabilized: {file_path.name}", level="warning")
            return

        # 3) Match.
        paper_id = self._match_pdf_to_paper(file_path)

        if paper_id:
            self._link_pdf_to_library(file_path, paper_id)
            self.processed_files.add(file_path.name)
            if self.ui is not None:
                self.ui.imported += 1
            return

        self._say(f"no paper match for {file_path.name}", level="warning")
        if self.unmatched_dir is not None:
            try:
                self.unmatched_dir.mkdir(parents=True, exist_ok=True)
                dest = self.unmatched_dir / file_path.name
                shutil.move(str(file_path), str(dest))
                self._say(f"MOVED unmatched -> {dest}", level="warning")
                self.processed_files.add(file_path.name)
                if self.ui is not None:
                    self.ui.unmatched += 1
            except OSError as exc:
                self._say(f"failed to move unmatched PDF: {exc}", level="error")

    def _match_pdf_to_paper(self, pdf_path: Path) -> Optional[str]:
        """Match downloaded PDF to paper_id.

        Strategies, in order:
        0. **Tab-origin** — if Playwright's ``page.on("download")`` already
           recorded ``filename → paper_id`` (the tab we opened *for* this
           paper just produced this download), use that. Most reliable.
        1. Exact match (filename or stem) against ``paper_id_map``.
        2. Substring match using stem (handles publisher tail-of-DOI names
           like ``s41598-020-76138-7.pdf`` against DOI ``10.1038/s41598-020-76138-7``).
        3. PDF content matching (/Title, DOI on page 1).
        """
        filename = pdf_path.name
        stem = pdf_path.stem  # without .pdf extension

        # Strategy 0: tab-origin (consume the entry — basename dedupe
        # ensures we won't match it twice).
        if filename in self.pending_downloads:
            pid = self.pending_downloads.pop(filename)
            self._say(
                f"MATCH    {self._label_for(pid):<35}  via tab origin",
                level="success",
            )
            return pid

        # Strategy 1: Exact match — try both the full name and the stem.
        for candidate in (filename, stem):
            if candidate in self.paper_id_map:
                return self.paper_id_map[candidate]

        # Strategy 2: Substring match. Use stem (no .pdf) so trailing
        # extensions don't break "DOI suffix in DOI" comparisons.
        for map_name, paper_id in self.paper_id_map.items():
            if not isinstance(map_name, str) or not map_name:
                continue
            if stem in map_name or map_name in stem:
                self._say(
                    f"MATCH    {self._label_for(paper_id):<35}  via stem '{stem}'",
                    level="success",
                )
                return paper_id

        # Strategy 2b: Normalized substring. Publisher filenames concat the
        # DOI tail and prepend "PII" or similar (e.g.
        # `PIIS1474442213700759.pdf` for DOI `10.1016/s1474-4422(13)70075-9`).
        # Strip non-alphanumeric and lowercase both sides, then substring.
        norm_stem = "".join(c for c in stem.lower() if c.isalnum())
        if norm_stem and len(norm_stem) >= 8:
            for map_name, paper_id in self.paper_id_map.items():
                if not isinstance(map_name, str) or not map_name:
                    continue
                norm_map = "".join(c for c in map_name.lower() if c.isalnum())
                if not norm_map or len(norm_map) < 8:
                    continue
                # Match if either contains the other (strict substring on
                # the normalized form). Symmetrical so PII prefix and DOI
                # registrant prefix both work.
                if norm_stem in norm_map or norm_map in norm_stem:
                    self._say(
                        f"MATCH    {self._label_for(paper_id):<35}  "
                        f"via normalized stem",
                        level="success",
                    )
                    return paper_id

        # Strategy 3: Extract and match metadata from PDF
        try:
            from pypdf import PdfReader

            reader = PdfReader(pdf_path)

            # Check PDF metadata
            if reader.metadata:
                pdf_title = reader.metadata.get("/Title", "").lower()

                # Match against paper titles
                for paper_id, title in self.paper_id_map.items():
                    if isinstance(title, str) and title.lower() in pdf_title:
                        logger.info(f"Title match from PDF metadata: {paper_id}")
                        return paper_id

            # Check first page for DOI
            if len(reader.pages) > 0:
                first_page = reader.pages[0].extract_text()

                # Look for DOI pattern
                import re

                doi_match = re.search(r"10\.\d{4,}/[^\s]+", first_page)
                if doi_match:
                    doi = doi_match.group()
                    for paper_id, paper_doi in self.paper_id_map.items():
                        if isinstance(paper_doi, str) and doi in paper_doi:
                            logger.info(f"DOI match from PDF content: {paper_id}")
                            return paper_id
        except Exception as e:
            logger.warning(f"Could not extract PDF metadata: {e}")

        return None

    def _link_pdf_to_library(self, pdf_path: Path, paper_id: str):
        """Move PDF to correct library location and update metadata."""
        try:
            # Get paper directory
            master_dir = self.config.path_manager.get_library_master_dir()
            paper_dir = master_dir / paper_id

            if not paper_dir.exists():
                logger.error(f"Paper directory not found: {paper_dir}")
                return

            # Read metadata to get proper filename
            metadata_file = paper_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)

                # Generate proper filename. Field paths used by the
                # current pipeline:
                #   metadata.basic.year       -> year
                #   metadata.basic.authors[0] -> first author (last token)
                #   metadata.publication.journal_short / .journal -> journal
                meta = metadata.get("metadata", {}) or {}
                basic = meta.get("basic", {}) or {}
                publication = meta.get("publication", {}) or {}

                year = basic.get("year") or "XXXX"

                first_author = basic.get("first_author_lastname") or ""
                if not first_author:
                    authors = basic.get("authors") or []
                    if authors and isinstance(authors[0], str):
                        tokens = authors[0].replace(",", " ").split()
                        first_author = tokens[-1] if tokens else "Unknown"
                    elif authors and isinstance(authors[0], dict):
                        first_author = (
                            authors[0].get("family")
                            or authors[0].get("last")
                            or authors[0].get("name")
                            or "Unknown"
                        )
                    else:
                        first_author = "Unknown"

                journal = (
                    publication.get("journal_short")
                    or publication.get("journal")
                    or basic.get("venue")
                    or basic.get("journal")
                    or "Unknown"
                )

                journal_clean = "".join(
                    c for c in journal if c.isalnum() or c in (" ", "-", "_")
                )[:50].strip()
                proper_name = f"{first_author}-{year}-{journal_clean}.pdf"
            else:
                # Fallback to original name
                proper_name = pdf_path.name

            # Move PDF to paper directory
            dest_path = paper_dir / proper_name
            shutil.move(str(pdf_path), str(dest_path))

            self._say(
                f"LINKED   {self._label_for(paper_id):<35}  {proper_name}",
                level="success",
            )
            self._say(f"  at {dest_path}", level="info")

            # Touch metadata for downstream watchers.
            if metadata_file.exists():
                metadata_file.touch()

            # Update project symlinks: SymlinkHandlersMixin.update_symlink
            # regenerates the `PDF-NN_CC-..._IF-..._YYYY_Author_Journal`
            # readable name from the current MASTER state (counts PDFs in
            # paper_dir) and replaces stale links. Run once per project
            # that contains this paper.
            try:
                projects = (metadata or {}).get("container", {}).get("projects") or []
                for proj in projects:
                    try:
                        self.library_manager.update_symlink(
                            master_storage_path=paper_dir,
                            project=proj,
                            metadata=metadata,
                        )
                    except Exception as exc:
                        self._say(
                            f"update_symlink failed for {proj}: {exc}",
                            level="warning",
                        )
            except Exception as exc:
                self._say(
                    f"could not update project symlinks: {exc}",
                    level="warning",
                )

        except Exception as e:
            self._say(f"failed to link PDF: {e}", level="error")

        except Exception as e:
            self._say(f"failed to link PDF: {e}", level="error")


def get_failed_papers(project: str, config: ScholarConfig) -> List[Dict]:
    """Get papers with failed downloads - reuse from open_browser.py"""
    from scitex_scholar.cli.open_browser import get_failed_papers as _get_failed

    return _get_failed(project, config)


def get_pending_papers(project: str, config: ScholarConfig) -> List[Dict]:
    """Get papers with pending downloads - reuse from open_browser.py"""
    from scitex_scholar.cli.open_browser import get_pending_papers as _get_pending

    return _get_pending(project, config)


_OVERLAY_INIT_TEMPLATE = r"""
(() => {
  // window.scitexWatch is injected by Python before this runs.
  function render() {
    if (!document.body || document.getElementById('scitex-watch-banner')) return;
    const w = window.scitexWatch || {};
    const paper = w.paper || null;

    if (!document.getElementById('scitex-breath-css')) {
      const s = document.createElement('style');
      s.id = 'scitex-breath-css';
      s.textContent = `@keyframes scitexBreath {
        0%,100% { box-shadow: 0 4px 16px rgba(107,143,179,.30); transform: scale(1); }
        50%     { box-shadow: 0 8px 28px rgba(107,143,179,.65); transform: scale(1.03); }
      }`;
      document.head.appendChild(s);
    }

    const banner = document.createElement('div');
    banner.id = 'scitex-watch-banner';
    banner.style.cssText = `
      position:fixed; top:20px; right:20px; z-index:2147483647;
      background:linear-gradient(135deg,#6b8fb3 0%,#7a9fc3 100%);
      color:#1a2332; padding:14px 18px; border:2px solid #506b7a;
      border-radius:10px;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      font-size:13px; font-weight:700;
      box-shadow:0 4px 16px rgba(0,0,0,.25);
      width:280px; max-width:280px;
      animation:scitexBreath 1.6s ease-in-out infinite;`;

    const esc = (t) => String(t || '').replace(/[&<>"']/g, c => (
      {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));

    let header, body;
    if (paper && paper.paper_id) {
      header = `📥 MONITORING [${esc(paper.paper_id)}]`;
      const yr = paper.year ? `${esc(paper.year)} · ` : '';
      body = `
        <div style="font-size:12px;font-weight:700;margin-bottom:4px;line-height:1.3;">
          ${esc(paper.title || '(no title)')}
        </div>
        <div style="font-size:10px;opacity:.8;font-weight:500;margin-bottom:8px;
                    word-break:break-all;">
          ${yr}DOI: ${esc(paper.doi || 'n/a')}
        </div>`;
    } else {
      header = '📥 MONITORING DOWNLOADS';
      body = `
        <div style="font-size:11px;opacity:.85;font-weight:500;margin-bottom:8px;
                    line-height:1.4;">
          New tab — any PDF you save will be auto-imported.
        </div>`;
    }

    banner.innerHTML = `
      <div style="font-size:13px;margin-bottom:6px;">${header}</div>
      ${body}
      <div style="font-size:10px;opacity:.7;margin-bottom:8px;font-weight:500;
                  word-break:break-all;">
        watch: ${esc(w.watchDir)}
      </div>
      <div style="font-size:10px;opacity:.6;margin-bottom:10px;font-weight:500;">
        Tip: any tab you open is also tracked.
      </div>
      <button id="scitex-stop-watch" style="
        width:100%;padding:8px 12px;background:#fff;color:#506b7a;border:none;
        border-radius:6px;font-weight:700;cursor:pointer;font-size:12px;">
        ✓ DONE — CLOSE THIS TAB
      </button>`;
    document.documentElement.appendChild(banner);
    banner.querySelector('#scitex-stop-watch').addEventListener('click', () => {
      banner.setAttribute('data-scitex-stop','true');
      banner.querySelector('#scitex-stop-watch').textContent = 'CLOSING...';
      banner.style.animation = 'none';
    });
  }

  // Render now if DOM is up; otherwise wait for body to appear.
  if (document.body) {
    render();
  } else {
    new MutationObserver((_, obs) => {
      if (document.body) { render(); obs.disconnect(); }
    }).observe(document.documentElement, {childList: true, subtree: true});
  }
})();
"""

_STOP_CHECK_JS = (
    "() => document.getElementById('scitex-watch-banner')"
    "?.getAttribute('data-scitex-stop') === 'true'"
)


def _make_init_script(watch_dir: str, paper: Optional[dict]) -> str:
    """Build a per-page init script that re-installs the banner on every load."""
    state = {"watchDir": str(watch_dir), "paper": paper or None}
    return f"window.scitexWatch = {json.dumps(state)};\n" + _OVERLAY_INIT_TEMPLATE


def _attach_overlay(page, watch_dir: str, paper: Optional[dict]) -> None:
    """Add init-script (handles future navigations) AND inject now (current DOM)."""
    script = _make_init_script(watch_dir, paper)
    try:
        page.add_init_script(script=script)
    except Exception:
        pass
    try:
        page.evaluate(f"() => {{ {script} }}")
    except Exception:
        pass


# ---------- Debug capture (mirrors scitex_browser.debugging.capture_debug_artifacts_async) ----------


_DEBUG_BASE = Path.home() / ".scitex" / "scholar" / "cache" / "debug" / "watch_sessions"


def _safe_label(s: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)[:80]


def _capture_debug(
    page,
    label: str,
    session_dir: Path,
    *,
    ui: Optional[TerminalUI] = None,
) -> None:
    """Save full-page screenshot + page HTML to ``session_dir``.

    Mirrors the convention used by ``UniversityOfMelbourneSSOAutomator``
    via ``scitex_browser.debugging.capture_debug_artifacts_async`` so the
    artifacts shape is consistent across the project.
    """
    safe = _safe_label(label)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    png = session_dir / f"{safe}_{ts}.png"
    html = session_dir / f"{safe}_{ts}.html"
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    try:
        page.screenshot(path=str(png), full_page=True, timeout=10_000)
        if ui is not None:
            ui.event(f"DEBUG  {png.name}", level="debug")
    except Exception as exc:
        if ui is not None:
            ui.event(f"screenshot failed: {exc}", level="debug")
    try:
        html.write_text(page.content(), encoding="utf-8")
    except Exception as exc:
        if ui is not None:
            ui.event(f"html save failed: {exc}", level="debug")


def _has_banner(page) -> bool:
    try:
        return bool(
            page.evaluate("() => !!document.getElementById('scitex-watch-banner')")
        )
    except Exception:
        return False


def _load_auth_cookies(
    config: "ScholarConfig", providers: Optional[List[str]] = None
) -> List[Dict]:
    """Read cached SSO cookies for the given providers.

    Mirrors the contract of ``BrowserAuthenticator.verify_authentication_async``
    but synchronously: reads ``~/.scitex/scholar/cache/auth/<provider>.json``
    directly (the cache is plain JSON), validates expiry, and returns the
    Playwright-shaped cookie list ready for ``context.add_cookies``.

    Returns an empty list if no valid session is cached.
    """
    if providers is None:
        providers = ["openathens", "shibboleth", "ezproxy"]

    out: List[Dict] = []
    for provider in providers:
        cache_path = Path(config.get_cache_auth_json(provider))
        if not cache_path.exists():
            continue
        try:
            data = json.loads(cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue

        # Expiry — soft check; some caches use cookie-level expires only.
        expiry_iso = data.get("expiry")
        if expiry_iso:
            try:
                if datetime.fromisoformat(expiry_iso) < datetime.now():
                    continue  # expired
            except ValueError:
                pass

        cookies = data.get("full_cookies") or []
        # Playwright expects each cookie to have either (domain & path) or
        # (url). Drop entries missing both fields.
        for c in cookies:
            if not isinstance(c, dict):
                continue
            if not (c.get("domain") and c.get("path")) and not c.get("url"):
                continue
            out.append(c)
    return out


def _label(meta: Optional[dict]) -> str:
    """Human-readable paper label like 'Smith 2020 Sci-Rep' for log messages.

    Falls back to paper_id when bibliographic fields are missing.
    """
    if not meta:
        return "unknown"
    author = (meta.get("first_author") or "").strip()
    year = str(meta.get("year") or "").strip()
    journal = (meta.get("journal") or "").strip()
    parts = [p for p in (author, year, journal) if p]
    if parts:
        return " ".join(parts)
    return meta.get("paper_id") or "unknown"


def _is_chrome_internal(url: Optional[str]) -> bool:
    """URLs where Chrome blocks userland script injection.

    Our ``add_init_script`` and ``evaluate`` calls are silently no-ops on
    these — skip overlay logic entirely or you get an infinite
    "banner missing → reinject" loop on chrome://new-tab-page etc.
    """
    if not url:
        return True
    u = url.lower()
    return (
        u.startswith("chrome://")
        or u.startswith("about:")
        or u.startswith("devtools://")
        or u.startswith("view-source:")
        or u.startswith("chrome-extension://")
        or u.startswith("edge://")
    )


def open_browser_with_monitoring(
    papers: List[Dict],
    project: str,
    config: ScholarConfig,
    profile: str = None,
    downloads_dir: Path = None,
    unmatched_dir: Optional[Path] = None,
) -> None:
    """Open browser and monitor downloads for auto-linking.

    Args:
        papers: List of paper metadata dicts
        project: Project name
        config: Scholar configuration
        profile: Browser profile name
        downloads_dir: Downloads directory to monitor
        unmatched_dir: If set, unmatched PDFs are moved here on detection.
    """
    from playwright.sync_api import sync_playwright

    if not papers:
        logger.info("No papers to open")
        return

    # Build paper_id map for download matching + per-paper overlay metadata
    paper_id_map = {}
    urls_to_open = []  # (paper_id, url, overlay_meta)

    for paper in papers:
        paper_id = paper.get("paper_id")
        if not paper_id:
            continue

        paper_id_map[paper_id] = paper_id
        title = paper.get("title") or ""
        doi = paper.get("doi") or ""
        if title:
            paper_id_map[title] = paper_id
        if doi:
            paper_id_map[doi] = paper_id

        # Pick the first viable URL.
        url = None
        if paper.get("openurl_resolved"):
            url = paper["openurl_resolved"][0]
        elif paper.get("url_publisher"):
            url = paper["url_publisher"]
        elif paper.get("url_doi"):
            url = paper["url_doi"]
        if not url:
            continue

        meta = {
            "paper_id": paper_id,
            "title": title,
            "doi": doi,
            "year": paper.get("year") or "",
            "first_author": paper.get("first_author") or "",
            "journal": paper.get("journal") or "",
        }
        urls_to_open.append((paper_id, url, meta))

    if not urls_to_open:
        logger.warning("No URLs to open")
        return

    # Get downloads directory
    if downloads_dir is None:
        downloads_dir = Path.home() / "Downloads"
    downloads_dir = Path(downloads_dir)

    if not downloads_dir.exists():
        logger.error(f"Downloads directory not found: {downloads_dir}")
        return

    logger.info(f"Monitoring downloads in: {downloads_dir}")
    logger.info(f"Opening {len(urls_to_open)} URLs in browser...")

    # Setup download monitor
    from scitex_scholar.storage._LibraryManager import LibraryManager

    library_manager = LibraryManager(config)

    # Second watch target: a dedicated dir Playwright is told to drop
    # downloads into via `downloads_path`. This catches downloads that the
    # browser routes through Playwright's interception path and never appear
    # in the user's Downloads dir.
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    playwright_dl_dir = (
        config.path_manager.get_cache_chrome_dir("system").parent
        / "playwright_downloads"
        / session_id
    )
    playwright_dl_dir.mkdir(parents=True, exist_ok=True)

    # Debug artifacts for this session — screenshots + HTML on every nav,
    # banner-missing event, and download. Mirrors the convention used by
    # paper-fetch's SSO automators.
    session_debug_dir = _DEBUG_BASE / session_id
    session_debug_dir.mkdir(parents=True, exist_ok=True)
    debug_log_path = session_debug_dir / "session.log"

    ui = TerminalUI()
    event_handler = DownloadMonitor(
        paper_id_map,
        library_manager,
        config,
        unmatched_dir=unmatched_dir,
        ui=ui,
    )
    # Seed paper_id → bibliographic meta so DownloadMonitor can render
    # human-readable labels (Smith 2020 Sci-Rep) instead of paper_ids.
    for _, _, _meta in urls_to_open:
        if _meta.get("paper_id"):
            event_handler.id_to_meta[_meta["paper_id"]] = _meta
    observer = Observer()
    observer.schedule(event_handler, str(downloads_dir), recursive=False)
    observer.schedule(event_handler, str(playwright_dl_dir), recursive=False)
    observer.start()

    logger.success(
        f"Download monitoring started. Watching:\n"
        f"  - {downloads_dir}\n"
        f"  - {playwright_dl_dir}"
    )

    # Get browser profile
    if profile:
        profile_dir = config.path_manager.get_cache_chrome_dir(profile)
    else:
        profile_dir = config.path_manager.get_cache_chrome_dir("system")

    profile_dir.mkdir(parents=True, exist_ok=True)

    ui.attach_debug_file(debug_log_path)
    ui.start(downloads_dir)

    # Pull cached SSO cookies (OpenAthens / Shibboleth / EZProxy) BEFORE
    # the browser launches. Without this, paywalled URLs see the user as
    # anonymous even though `~/.scitex/scholar/cache/auth/<p>.json` holds
    # a valid session. Mirrors the BrowserAuthenticator pattern.
    auth_cookies = _load_auth_cookies(config)
    if auth_cookies:
        ui.event(
            f"AUTH     loaded {len(auth_cookies)} cookies from cached SSO session",
            level="success",
        )
    else:
        ui.event(
            "AUTH     no cached SSO session found — paywalled URLs will be "
            "anonymous (run `scitex-scholar auth login` first)",
            level="warning",
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=False,
                accept_downloads=True,
                downloads_path=str(playwright_dl_dir),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=UserAgentClientHint",
                ],
            )

            if auth_cookies:
                try:
                    browser.add_cookies(auth_cookies)
                    ui.event(
                        f"AUTH     injected {len(auth_cookies)} cookies",
                        level="success",
                    )
                except Exception as exc:
                    ui.event(
                        f"AUTH     add_cookies failed: {exc}",
                        level="warning",
                    )

            # CRITICAL: Playwright intercepts downloads. The tmp file under
            # downloads_path has a UUID name (no .pdf extension) so our
            # handler ignores it. We must save explicitly with a proper
            # filename into a Linux-native watched dir.
            #
            # Save twice:
            #   1. playwright_dl_dir/<suggested>   ← inotify fires here (WSL ok)
            #   2. downloads_dir/<suggested>      ← user's expected location
            #      (often /mnt/c/.../Downloads on WSL, where inotify is
            #      silent — fine, primary detection path is #1).
            # Closure-builder so the handler knows which Page (and therefore
            # which paper_id) the download originated from.
            def _make_on_download(pg):
                def _on_download(download):
                    suggested = download.suggested_filename or "download.pdf"
                    pid = page_meta.get(id(pg), {}).get("paper_id") if pg else None

                    # Tab-origin association: when DownloadMonitor sees this
                    # filename land on disk, it'll match by paper_id directly.
                    if pid and pid != "new":
                        event_handler.pending_downloads[suggested] = pid
                        pg_meta = page_meta.get(id(pg), {}) if pg else {}
                        ui.event(
                            f"DOWNLOAD start  {_label(pg_meta):<35}  {suggested}",
                            level="success",
                        )
                    else:
                        ui.event(
                            f"DOWNLOAD start  (unknown tab)            {suggested}",
                            level="success",
                        )

                    primary = playwright_dl_dir / suggested
                    try:
                        download.save_as(str(primary))
                        ui.event(f"DOWNLOAD saved -> {primary}", level="success")
                    except Exception as exc:
                        ui.event(
                            f"download.save_as primary failed: {exc}",
                            level="warning",
                        )
                    try:
                        download.save_as(str(downloads_dir / suggested))
                    except Exception as exc:
                        ui.event(
                            f"download.save_as user copy skipped: {exc}",
                            level="debug",
                        )

                return _on_download

            # Generic context-level fallback (some Playwright versions surface
            # download on context too; caller info isn't available there).
            def _on_download_generic(download):
                _make_on_download(None)(download)

            # NOTE: In Playwright sync API, the `download` event is delivered
            # on Page (not BrowserContext). Subscribe per-page below.
            #
            # Some Playwright versions DO surface it on context too; subscribe
            # there as well so we get the event whichever way it fires (the
            # _on_download body is idempotent — first save_as wins).
            # Per-page metadata so download handlers can label by paper_id.
            page_meta: Dict[int, dict] = {}

            try:
                browser.on("download", _on_download_generic)
            except Exception:
                pass

            def _attach_download_handler(pg) -> None:
                try:
                    pg.on("download", _make_on_download(pg))
                except Exception:
                    pass

            def _meta_for(pg) -> dict:
                return page_meta.get(id(pg), {"paper_id": "new"})

            def _attach_nav_capture(pg) -> None:
                # NOTE: Per-nav full-page screenshots ran the browser into
                # the ground (sync Playwright blocks the browser thread on
                # screenshot, fonts.ready, etc.). Drop the screenshot; just
                # log the navigation at debug level. We still capture
                # screenshots on banner-missing and DONE click.
                def _on_nav(frame):
                    try:
                        if frame != pg.main_frame:
                            return
                    except Exception:
                        return
                    try:
                        url = frame.url
                    except Exception:
                        url = ""
                    if _is_chrome_internal(url):
                        return
                    pid = _meta_for(pg).get("paper_id", "new")
                    ui.event(f"NAV [{pid}] {url[:80]}", level="debug")

                try:
                    pg.on("framenavigated", _on_nav)
                except Exception:
                    pass

            def _on_new_page(page):
                # New tabs are often popups spawned by a publisher's
                # "Download PDF" button. Playwright's Page.opener() returns
                # the page that triggered window.open(), so we inherit
                # paper_id from there — the popup carries the same paper.
                inherited = None
                try:
                    opener = page.opener()
                except Exception:
                    opener = None
                if opener is not None:
                    om = page_meta.get(id(opener))
                    if om:
                        page_meta[id(page)] = om
                        inherited = om.get("paper_id")
                _attach_nav_capture(page)
                _attach_download_handler(page)
                if inherited:
                    ui.event(
                        f"NEWTAB inherits [{inherited}] from opener",
                        level="debug",
                    )
                else:
                    ui.event("user-opened tab tracked", level="debug")

            browser.on("page", _on_new_page)

            opened_pages = []

            if browser.pages:
                first = browser.pages[0]
            else:
                first = browser.new_page()

            # NOTE: in-page banner injection is disabled because chrome://
            # blocks it, publisher SPAs and pop-up-blocker extensions strip
            # it, and we don't need it for matching — tab-origin download
            # mapping handles paper_id assignment correctly.
            if urls_to_open:
                paper_id, url, meta = urls_to_open[0]
                page_meta[id(first)] = meta
                _attach_nav_capture(first)
                _attach_download_handler(first)
                first.goto(url)
                ui.event(
                    f"OPENED  {_label(meta):<35}  {url[:60]}",
                    level="info",
                )
                opened_pages.append(first)

            for paper_id, url, meta in urls_to_open[1:]:
                new_page = browser.new_page()
                page_meta[id(new_page)] = meta
                _attach_nav_capture(new_page)
                _attach_download_handler(new_page)
                new_page.goto(url)
                ui.event(
                    f"OPENED  {_label(meta):<35}  {url[:60]}",
                    level="info",
                )
                opened_pages.append(new_page)

            ui.event(
                f"READY {len(urls_to_open)} tab(s) open. "
                f"Debug: {session_debug_dir}. "
                "Click DONE in a tab to close it; Ctrl+C to exit.",
                level="success",
            )

            # CRITICAL: in sync Playwright, page.on("download", ...) and
            # other event callbacks are dispatched ONLY when the sync API
            # is called. A bare `time.sleep` does NOT pump the event queue,
            # so download events appear delayed (sometimes only flushed by
            # browser.close on Ctrl+C). Use page.wait_for_timeout to pump
            # the connection ~every second; events fire live.
            try:
                while True:
                    pages = list(browser.pages)
                    if not pages:
                        ui.event("all tabs closed", level="info")
                        break
                    try:
                        pages[0].wait_for_timeout(1000)
                    except Exception:
                        # Page may have closed mid-wait — fall back to
                        # plain sleep so we don't spin.
                        time.sleep(1.0)
            except KeyboardInterrupt:
                ui.event("Ctrl+C received", level="info")
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    finally:
        observer.stop()
        observer.join()
        ui.stop()
        logger.success(
            f"Done. detected={ui.detected} imported={ui.imported} "
            f"unmatched={ui.unmatched}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Open browser with download monitoring and auto-linking"
    )
    parser.add_argument(
        "--project", required=True, help="Project name (e.g., neurovista, pac)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Open both failed and pending PDFs"
    )
    parser.add_argument(
        "--pending", action="store_true", help="Open only pending (not attempted) PDFs"
    )
    parser.add_argument(
        "--profile", help="Browser profile name to use (default: system)"
    )
    parser.add_argument(
        "--downloads-dir",
        type=Path,
        help="Downloads directory to monitor (default: ~/Downloads)",
    )

    args = parser.parse_args()

    # Initialize config
    config = ScholarConfig()

    # Get papers based on flags
    papers = []

    if args.all or args.pending:
        pending = get_pending_papers(args.project, config)
        logger.info(f"Found {len(pending)} pending papers")
        papers.extend(pending)

    if args.all or not args.pending:
        failed = get_failed_papers(args.project, config)
        logger.info(f"Found {len(failed)} failed papers")
        papers.extend(failed)

    if not papers:
        logger.warning(f"No papers found for project: {args.project}")
        return

    # Show summary
    logger.info(f"\nOpening {len(papers)} papers with download monitoring:")
    for i, paper in enumerate(papers[:10], 1):
        title = paper.get("title", "Unknown")[:60]
        logger.info(f"  {i}. {title}...")
    if len(papers) > 10:
        logger.info(f"  ... and {len(papers) - 10} more")

    # Open browser with monitoring
    open_browser_with_monitoring(
        papers,
        args.project,
        config,
        profile=args.profile,
        downloads_dir=args.downloads_dir,
    )


if __name__ == "__main__":
    main()
