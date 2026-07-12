#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/skills.py

"""``skills`` command group + ``list-python-apis`` for the Scholar CLI.

Extracted verbatim from ``_cli_main.py`` (which had grown past the repo's
512-line limit) so the module stays under that gate. See
``GITIGNORED/REFACTORING.md``. Kept together because both live under the
"Skills" entry of ``COMMAND_CATEGORIES`` in ``_cli_main.py``.

Registered by ``_cli_main`` via ``from ._cli.skills import skills,
list_python_apis`` + ``cli.add_command(skills)`` /
``cli.add_command(list_python_apis)``.

Note: ``_skills_dir()`` resolves relative to *this* file's location, one
directory deeper than the original ``_cli_main.py`` — hence the extra
``.parent`` to still land on ``src/scitex_scholar/_skills/scitex-scholar``.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import click

from .._cli_main import CONTEXT_SETTINGS

# ---------------------------------------------------------------------------
# Group: skills
# ---------------------------------------------------------------------------


def _skills_dir() -> Path:
    return Path(__file__).parent.parent / "_skills" / "scitex-scholar"


@click.group(context_settings=CONTEXT_SETTINGS)
def skills() -> None:
    """Bundled skill leaves."""


@skills.command("list")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def skills_list(as_json):
    """List bundled skill leaf names.

    \b
    Example:
      $ scitex-scholar skills list
    """
    d = _skills_dir()
    if not d.is_dir():
        if as_json:
            click.echo(_json.dumps([]))
        return
    names = sorted(p.stem for p in d.glob("*.md"))
    if as_json:
        click.echo(_json.dumps(names))
        return
    for n in names:
        click.echo(n)


@skills.command("get")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="JSON output.")
def skills_get(name, as_json):
    """Print the contents of a skill leaf.

    \b
    Example:
      $ scitex-scholar skills get 04_cli-reference
      $ scitex-scholar skills get 04_cli-reference --json
    """
    d = _skills_dir()
    p = d / f"{name}.md"
    if not p.exists():
        raise click.ClickException(f"Skill not found: {name} (looked in {d})")
    body = p.read_text()
    if as_json:
        click.echo(_json.dumps({"name": name, "path": str(p), "body": body}, indent=2))
    else:
        click.echo(body)


@skills.command("install")
@click.option(
    "--target",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Install dir (default: ~/.claude/skills/scitex-scholar).",
)
@click.option(
    "--symlink/--copy",
    default=True,
    help="Symlink (default) or copy the skills directory.",
)
@click.option("--force", is_flag=True, help="Replace existing target.")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", "-y", is_flag=True)
def skills_install(target, symlink, force, dry_run, yes):
    """Install bundled skills to ~/.claude/skills/scitex-scholar/.

    \b
    Example:
      $ scitex-scholar skills install
      $ scitex-scholar skills install --copy --force
    """
    src = _skills_dir()
    dst = (
        Path(target) if target else Path("~/.claude/skills/scitex-scholar").expanduser()
    )
    if dry_run:
        click.echo(f"DRY RUN — would {'symlink' if symlink else 'copy'} {src} -> {dst}")
        return
    if not src.is_dir():
        raise click.ClickException(f"Skills source missing: {src}")
    if dst.exists() or dst.is_symlink():
        if not force:
            raise click.ClickException(f"{dst} exists; pass --force to replace")
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            import shutil

            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if symlink:
        dst.symlink_to(src.resolve())
    else:
        import shutil

        shutil.copytree(src, dst)
    click.echo(f"Installed skills -> {dst}")


# ---------------------------------------------------------------------------
# list-python-apis
# ---------------------------------------------------------------------------


@click.command("list-python-apis", context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", count=True, help="-v: signatures.")
@click.option("--json", "as_json", is_flag=True)
def list_python_apis(verbose, as_json):
    """List public callables in scitex_scholar.__all__.

    \b
    Example:
      $ scitex-scholar list-python-apis
      $ scitex-scholar list-python-apis -v
    """
    import inspect

    import scitex_scholar as ss

    names = list(getattr(ss, "__all__", []))
    out: list[dict[str, str]] = []
    for n in names:
        if n.startswith("_") or n == "__version__":
            continue
        try:
            obj = getattr(ss, n)
        except Exception:
            obj = None
        sig = ""
        if verbose and callable(obj):
            try:
                sig = str(inspect.signature(obj))
            except (TypeError, ValueError):
                sig = ""
        out.append({"name": n, "signature": sig})

    if as_json:
        click.echo(_json.dumps(out, indent=2))
        return
    for entry in out:
        if verbose and entry["signature"]:
            click.echo(f"{entry['name']}{entry['signature']}")
        else:
            click.echo(entry["name"])


# EOF
