#!/usr/bin/env python3
"""Shell tab-completion via a sac-owned drop-in file (contract v1).

``scitex-scholar completion install`` writes the click-generated
completion script to the canonical cache path and prints that path::

    $SCITEX_DIR/scholar/runtime/completion/scitex-scholar

``$SCITEX_DIR`` defaults to ``~/.scitex``. This command never touches
shell rc files — sourcing the drop-in from the user's
shell rc is left to the user (or to sac-managed shell setup).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import click

PROG_NAME = "scitex-scholar"

SHELLS = ["bash", "zsh", "fish"]


def _complete_var(prog_name: str) -> str:
    """Click's autocompletion env var: ``_<UPPER_PROG>_COMPLETE``."""
    return "_" + prog_name.upper().replace("-", "_") + "_COMPLETE"


def _scitex_dir() -> Path:
    """Resolve ``$SCITEX_DIR`` (default ``~/.scitex``)."""
    return Path(os.environ.get("SCITEX_DIR", os.path.expanduser("~/.scitex")))


def _pkg_short(prog_name: str) -> str:
    """Strip a leading ``scitex-`` prefix; other names use the full name."""
    if prog_name.startswith("scitex-"):
        return prog_name[len("scitex-") :]
    return prog_name


def _cache_path(prog_name: str = PROG_NAME) -> Path:
    """Canonical drop-in: ``$SCITEX_DIR/<short>/runtime/completion/<prog>``."""
    return _scitex_dir() / _pkg_short(prog_name) / "runtime" / "completion" / prog_name


def _generate_script(root_group: click.Group, shell: str, prog_name: str) -> str:
    """Return the click-generated completion script for ``shell`` in-process."""
    from click.shell_completion import get_completion_class

    comp_cls = get_completion_class(shell)
    if comp_cls is None:
        raise click.ClickException(f"Unsupported shell: {shell}")
    completer = comp_cls(root_group, {}, prog_name, _complete_var(prog_name))
    script = completer.source().strip()
    if not script:
        raise click.ClickException(
            f"Failed to generate {shell} completion script for {prog_name}."
        )
    return script


def _write_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (tmp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


@click.group("completion")
def completion() -> None:
    """Shell tab-completion via a drop-in file.

    \b
    Examples:
      $ scitex-scholar completion install
      $ scitex-scholar completion install --shell bash
      $ scitex-scholar completion status
    """


@completion.command("install")
@click.option(
    "--shell",
    type=click.Choice(SHELLS),
    default="bash",
    show_default=True,
    help="Completion script variant to write.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Accept the install without prompting (install is non-interactive).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview the target drop-in path without writing.",
)
@click.pass_context
def install_cmd(ctx: click.Context, shell: str, yes: bool, dry_run: bool) -> None:
    """Write the completion drop-in file and print its path.

    \b
    Examples:
      $ scitex-scholar completion install
      $ scitex-scholar completion install --shell zsh
      $ source ~/.scitex/scholar/runtime/completion/scitex-scholar
    """
    del yes  # accepted for non-interactive use; install never prompts
    cache = _cache_path(PROG_NAME)
    if dry_run:
        click.echo(f"Would write completion to {cache}")
        return
    root = ctx.find_root().command
    if not isinstance(root, click.Group):
        raise click.ClickException("Cannot locate the root command group.")
    script = _generate_script(root, shell, PROG_NAME)
    _write_atomic(cache, script)
    click.echo(str(cache))


@completion.command("status")
def status_cmd() -> None:
    """Report whether the completion drop-in file exists.

    \b
    Examples:
      $ scitex-scholar completion status
    """
    cache = _cache_path(PROG_NAME)
    if cache.is_file():
        click.echo(f"Completion installed: {cache}")
    else:
        click.echo(f"Completion not installed: {cache}")
        click.echo("Install with: scitex-scholar completion install")


def register_completion_commands(cli_group: click.Group) -> None:
    """Register the ``completion`` group on the main CLI group."""
    cli_group.add_command(completion)
