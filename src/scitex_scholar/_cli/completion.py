#!/usr/bin/env python3
"""Shell tab-completion via a sac-owned drop-in file (contract v1).

``scitex-scholar completion install`` writes the click-generated
completion script to the canonical cache path and prints that path::

    $SCITEX_DIR/scholar/runtime/completion/scitex-scholar

``$SCITEX_DIR`` defaults to ``~/.scitex``. This command never touches
shell rc files — sourcing the drop-in from the user's
shell rc is left to the user (or to sac-managed shell setup).

The legacy top-level spellings ``install-shell-completion`` and
``print-shell-completion`` stay as hidden Phase W warn-forward aliases
(audit §1a still requires those names on the root group).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import click

from ._scaffolding import (
    _warn_deprecated,
    spec_command_kwargs,
    spec_group_kwargs,
)

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


def _root_group(ctx: click.Context) -> click.Group:
    """Resolve the root command group from a leaf context."""
    root = ctx.find_root().command
    if not isinstance(root, click.Group):
        raise click.ClickException("Cannot locate the root command group.")
    return root


def _run_install(ctx: click.Context, shell: str, dry_run: bool) -> None:
    """Write the completion drop-in file and echo its path (shared impl)."""
    cache = _cache_path(PROG_NAME)
    if dry_run:
        click.echo(f"Would write completion to {cache}")
        return
    script = _generate_script(_root_group(ctx), shell, PROG_NAME)
    _write_atomic(cache, script)
    click.echo(str(cache))


def _run_status(as_json: bool) -> None:
    """Report whether the completion drop-in file exists (shared impl)."""
    cache = _cache_path(PROG_NAME)
    installed = cache.is_file()
    if as_json:
        click.echo(json.dumps({"installed": installed, "path": str(cache)}))
        return
    if installed:
        click.echo(f"Completion installed: {cache}")
    else:
        click.echo(f"Completion not installed: {cache}")
        click.echo("Install with: scitex-scholar completion install")


@click.group(
    "completion",
    **spec_group_kwargs(
        "Shell tab-completion via a drop-in file.",
        description=(
            "Writes the click-generated script to "
            "$SCITEX_DIR/scholar/runtime/completion/scitex-scholar; "
            "never touches shell rc files.",
        ),
    ),
)
def completion() -> None:
    """Shell tab-completion via a drop-in file."""


@completion.command(
    "install",
    **spec_command_kwargs(
        "Write the completion drop-in file and print its path.",
        examples=(
            ("{prog} completion install", "Write the bash drop-in file."),
            ("{prog} completion install --shell zsh", "Write the zsh drop-in file."),
            ("{prog} completion install --dry-run", "Preview the target path."),
        ),
    ),
)
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
    """Write the completion drop-in file and print its path."""
    del yes  # accepted for non-interactive use; install never prompts
    _run_install(ctx, shell, dry_run)


@completion.command(
    "status",
    **spec_command_kwargs(
        "Report whether the completion drop-in file exists.",
        examples=(
            ("{prog} completion status", "Human-readable wiring report."),
            ("{prog} completion status --json", "Machine-readable wiring report."),
        ),
    ),
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit the wiring report as JSON.",
)
def status_cmd(as_json: bool) -> None:
    """Report whether the completion drop-in file exists."""
    _run_status(as_json)


@click.command(
    "install-shell-completion",
    hidden=True,
    **spec_command_kwargs(
        "Deprecated alias for 'completion install'.",
        examples=(
            ("{prog} install-shell-completion", "Same as 'completion install'."),
        ),
    ),
)
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
def legacy_install_shell_completion(
    ctx: click.Context, shell: str, yes: bool, dry_run: bool
) -> None:
    """Deprecated alias for 'completion install' (Phase W warn-forward)."""
    del yes  # accepted for non-interactive use; install never prompts
    _warn_deprecated("install-shell-completion", "completion install")
    _run_install(ctx, shell, dry_run)


@click.command(
    "print-shell-completion",
    hidden=True,
    **spec_command_kwargs(
        "Deprecated alias printing the completion script to stdout.",
        examples=(
            ("{prog} print-shell-completion", "Print the bash script."),
        ),
    ),
)
@click.option(
    "--shell",
    type=click.Choice(SHELLS),
    default="bash",
    show_default=True,
    help="Completion script variant to print.",
)
@click.pass_context
def legacy_print_shell_completion(ctx: click.Context, shell: str) -> None:
    """Deprecated alias printing the completion script (Phase W warn-forward)."""
    _warn_deprecated("print-shell-completion", "completion install --dry-run")
    click.echo(_generate_script(_root_group(ctx), shell, PROG_NAME))


def register_completion_commands(cli_group: click.Group) -> None:
    """Register the ``completion`` group plus legacy aliases on ``cli_group``."""
    cli_group.add_command(completion)
    cli_group.add_command(legacy_install_shell_completion)
    cli_group.add_command(legacy_print_shell_completion)
