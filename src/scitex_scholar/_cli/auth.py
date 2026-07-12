#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/auth.py

"""``auth`` command group for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``.

Registered by ``_cli_main`` via ``from ._cli.auth import auth`` +
``cli.add_command(auth)``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import click

from .._cli_main import CONTEXT_SETTINGS

# ---------------------------------------------------------------------------
# Group: auth — institutional SSO session management
# ---------------------------------------------------------------------------


@click.group(context_settings=CONTEXT_SETTINGS)
def auth() -> None:
    """Institutional SSO authentication (OpenAthens / EZProxy / Shibboleth).

    The cached session lives at
    `~/.scitex/scholar/cache/auth/<provider>.json`. It is refreshed
    lazily by `paper fetch`, but these commands let you inspect or
    drive the lifecycle directly — useful for debugging the SSO
    automator and pre-warming sessions for batch jobs.
    """


def _auth_cache_paths() -> list[Path]:
    """All cached auth session files."""
    from scitex_scholar.config import ScholarConfig

    auth_dir = ScholarConfig().path_manager.get_cache_auth_dir()
    if not auth_dir.exists():
        return []
    return sorted(p for p in auth_dir.glob("*.json") if p.is_file())


@auth.command("status", context_settings=CONTEXT_SETTINGS)
@click.option("--json", "as_json", is_flag=True)
def auth_status(as_json: bool) -> int:
    """Show cached SSO session state.

    \b
    Exit code:
      0  at least one session is valid
      1  no session, or all expired

    \b
    Example:
      $ scitex-scholar auth status
      $ scitex-scholar auth status --json
    """
    import datetime
    import json
    import time

    paths = _auth_cache_paths()
    rows: list[dict[str, Any]] = []
    any_valid = False
    for p in paths:
        try:
            data = json.loads(p.read_text())
        except Exception as e:
            rows.append({"provider": p.stem, "status": "unreadable", "error": str(e)})
            continue
        # Try common expiry shapes: top-level "expires_at" / cookie list.
        expiry = data.get("expires_at") or data.get("expiry")
        cookie_count = len(data.get("cookies", []))
        if expiry is None and isinstance(data.get("cookies"), list):
            # Fall back: max cookie expiry.
            cookie_expiries = [
                c.get("expires", 0)
                for c in data["cookies"]
                if isinstance(c, dict) and c.get("expires")
            ]
            expiry = max(cookie_expiries) if cookie_expiries else None
        if expiry is None:
            status = "valid (unknown expiry)"
            any_valid = True
        elif float(expiry) > time.time():
            status = "valid"
            any_valid = True
        else:
            status = "expired"
        rows.append(
            {
                "provider": p.stem,
                "status": status,
                "cookies": cookie_count,
                "expires_at": (
                    datetime.datetime.fromtimestamp(float(expiry)).isoformat()
                    if expiry
                    else None
                ),
                "cache_path": str(p),
            }
        )

    if as_json:
        click.echo(json.dumps({"sessions": rows, "any_valid": any_valid}, indent=2))
    elif not rows:
        click.echo("No cached sessions found.")
    else:
        for r in rows:
            click.echo(
                f"{r['provider']:<15} {r['status']:<25} "
                f"cookies={r.get('cookies', '?')} expires={r.get('expires_at') or 'unknown'}"
            )

    return 0 if any_valid else 1


@auth.command("logout", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default=None, help="Specific provider (default: all).")
@click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive.")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted.")
def auth_logout(provider: str | None, yes: bool, dry_run: bool) -> int:
    """Clear cached SSO session(s) — forces next call to re-authenticate.

    \b
    Example:
      $ scitex-scholar auth logout
      $ scitex-scholar auth logout --provider openathens
      $ scitex-scholar auth logout --dry-run
    """
    paths = _auth_cache_paths()
    if provider:
        paths = [p for p in paths if p.stem == provider]
    if not paths:
        click.echo("No cached sessions to clear.")
        return 0
    click.echo(f"Will clear: {[str(p) for p in paths]}")
    if dry_run:
        return 0
    if not yes:
        click.echo(
            "Refusing to proceed without --yes/-y "
            "(mutating action; non-interactive by design).",
            err=True,
        )
        return 2
    cleared = 0
    for p in paths:
        try:
            p.unlink()
            cleared += 1
            click.echo(f"  cleared: {p}")
        except OSError as e:
            click.echo(f"  failed:  {p}: {e}", err=True)
    # Also clear sso_sessions/ directory if present.
    from scitex_scholar.config import ScholarConfig

    sso_dir = ScholarConfig().path_manager.get_cache_auth_dir() / "sso_sessions"
    if sso_dir.exists() and (provider is None or provider == "sso_sessions"):
        try:
            import shutil

            shutil.rmtree(sso_dir)
            click.echo(f"  cleared: {sso_dir}/")
        except OSError as e:
            click.echo(f"  failed:  {sso_dir}: {e}", err=True)
    click.echo(f"Cleared {cleared} session file(s).")
    return 0


@auth.command("login", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default="openathens", help="Provider to authenticate.")
@click.option(
    "--browser-mode",
    type=click.Choice(["stealth", "interactive"]),
    default="stealth",
)
def auth_login(provider: str, browser_mode: str) -> int:
    """Trigger SSO login flow now — pre-warm the cached session.

    \b
    Example:
      $ scitex-scholar auth login
      $ scitex-scholar auth login --browser-mode interactive
    """
    from scitex_scholar.auth import ScholarAuthManager

    async def _go() -> int:
        mgr = ScholarAuthManager()
        ok = await mgr.ensure_authenticate_async()
        return 0 if ok else 1

    return asyncio.run(_go())


@auth.command("refresh", context_settings=CONTEXT_SETTINGS)
@click.option("--provider", default=None, help="Specific provider (default: all).")
@click.pass_context
def auth_refresh(ctx: click.Context, provider: str | None) -> int:
    """Force re-login: equivalent to `auth logout --yes` followed by `auth login`.

    \b
    Examples:
      $ scitex-scholar auth refresh
      $ scitex-scholar auth refresh --provider openathens
    """
    rc = ctx.invoke(auth_logout, provider=provider, yes=True, dry_run=False)
    if rc != 0:
        return rc
    return ctx.invoke(
        auth_login, provider=provider or "openathens", browser_mode="stealth"
    )


# EOF
