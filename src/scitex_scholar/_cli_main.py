#!/usr/bin/env python3
# File: src/scitex_scholar/__main__.py

"""Scholar CLI entry point — Click-based noun-verb subcommand interface.

Top-level groups:

- ``paper``   {fetch, fetch-batch}                       — fetch paper(s) into the library
- ``bibtex``  {import}                                   — import a BibTeX file
- ``pdf``     {highlight}                                — PDF post-processing
- ``library`` {link-project-tree, materialize, dematerialize, db}
- ``mcp``     {start, list-tools, doctor, install}       — MCP server commands
- ``skills``  {list, get, install}                       — bundled skill leaves
- ``list-python-apis``                                   — print public API names

Pre-1.3.0 top-level forms (``single``, ``parallel``, ``bibtex --bibtex …``,
``highlight``, ``link-project-tree``, ``materialize``, ``dematerialize``,
``db``) remain as **hidden deprecation aliases**: they parse cleanly,
emit a one-line yellow warning to stderr, and dispatch to the new handler.

This module itself only holds the root ``cli`` group, its shared
scaffolding (``_CategorizedGroup`` / ``CONTEXT_SETTINGS`` / ...), and the
process entry point. Each command group was extracted into its own
``._cli.<name>`` module (this file had grown past the repo's 512-line
limit) — see ``GITIGNORED/REFACTORING.md`` and ``src/scitex_scholar/_cli/``.
"""

from __future__ import annotations

import sys

import click


# TODO(scitex-dev): import scitex_dev.click_helpers.CategorizedGroup once
# available; currently scitex-dev does not export it, so we fall back to
# plain click.Group.
class _CategorizedGroup(click.Group):
    """Click Group that renders ``--help`` commands grouped by section.

    Subclass and set ``SECTIONS`` to ``[("Section name", ["cmd1", ...]), ...]``.
    Commands not listed in any section land under ``[Other]``.
    """

    SECTIONS: list = []

    def format_commands(self, ctx, formatter):
        commands = {
            n: c for n, c in self.commands.items() if not getattr(c, "hidden", False)
        }
        seen: set = set()
        with formatter.section("Commands"):
            for label, names in self.SECTIONS:
                rows = []
                for name in names:
                    cmd = commands.get(name)
                    if cmd is None:
                        continue
                    rows.append((name, cmd.get_short_help_str()))
                    seen.add(name)
                if rows:
                    formatter.write(f"\n  [{label}]\n")
                    for n, s in rows:
                        formatter.write(f"    {n:<26}{s}\n")
            other = sorted(n for n in commands if n not in seen)
            if other:
                formatter.write("\n  [Other]\n")
                for n in other:
                    formatter.write(f"    {n:<26}{commands[n].get_short_help_str()}\n")


# Top-level cli: same renderer with workflow/dev split. Replaces the
# unused scitex-dev `CategorizedGroup` import that fell back to plain
# click.Group when scitex-dev didn't actually export it.
class _RootGroup(_CategorizedGroup):
    SECTIONS = [
        ("Workflow", ["paper", "bibtex", "pdf", "library", "auth"]),
        (
            "Dev",
            [
                "list-python-apis",
                "mcp",
                "skills",
                "install-shell-completion",
                "print-shell-completion",
            ],
        ),
    ]


CategorizedGroup = _RootGroup  # used by @click.group(cls=...)


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


class _IntOrHelp(click.ParamType):
    """An integer option type that treats ``-h``/``--help`` as a help request.

    Click consumes the token after a value-taking option as that option's
    value, so ``--batch-size -h`` would otherwise fail with "not a valid
    integer". Here we detect a help token and print the command help instead.
    """

    name = "integer"

    def convert(self, value, param, ctx):
        if isinstance(value, str) and value in ("-h", "--help"):
            click.echo(ctx.get_help())
            ctx.exit()
        try:
            return int(value)
        except (TypeError, ValueError):
            self.fail(f"{value!r} is not a valid integer", param, ctx)


_INT_OR_HELP = _IntOrHelp()

COMMAND_CATEGORIES = [
    ("Paper", ["paper"]),
    ("Bibtex", ["bibtex"]),
    ("PDF", ["pdf"]),
    ("Library", ["library"]),
    ("Auth", ["auth"]),
    ("MCP", ["mcp"]),
    ("Skills", ["skills", "list-python-apis"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _warn_deprecated(old_form: str, new_form: str) -> None:
    """Emit a one-line yellow deprecation warning to stderr."""
    click.secho(
        f"DeprecationWarning: 'scitex-scholar {old_form}' is deprecated; "
        f"use 'scitex-scholar {new_form}' (will be removed in 1.4.0).",
        fg="yellow",
        err=True,
    )


def _print_command_help(
    cmd: click.Command, prefix: str, parent_ctx: click.Context
) -> None:
    """Recursively print help for a command and its subcommands."""
    click.echo(f"\n{'=' * 50}")
    click.echo(prefix)
    click.echo("=" * 50)
    sub_ctx = click.Context(cmd, info_name=prefix.split()[-1], parent=parent_ctx)
    click.echo(cmd.get_help(sub_ctx))
    if isinstance(cmd, click.Group):
        for sub_name, sub_cmd in sorted(cmd.commands.items()):
            if getattr(sub_cmd, "hidden", False):
                continue
            _print_command_help(sub_cmd, f"{prefix} {sub_name}", sub_ctx)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(
    cls=CategorizedGroup,
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    help=(
        "SciTeX Scholar — scientific literature management.\n\n"
        "Storage layout: ~/.scitex/scholar/library/MASTER/{8DIGITID}/ "
        "(canonical), {project}/ (symlinks)."
    ),
)
@click.version_option(None, "-V", "--version", package_name="scitex-scholar")
@click.option(
    "--help-recursive",
    is_flag=True,
    help="Show help for every command and subcommand.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON output where supported.",
)
@click.pass_context
def cli(ctx: click.Context, help_recursive: bool, as_json: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json

    if help_recursive:
        click.echo(cli.get_help(ctx))
        for name, cmd in sorted(cli.commands.items()):
            if getattr(cmd, "hidden", False):
                continue
            _print_command_help(cmd, f"scitex-scholar {name}", ctx)
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Group: paper  (extracted -> ._cli.paper; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.paper import paper  # noqa: E402  (after `cli` is defined above)

cli.add_command(paper)


# ---------------------------------------------------------------------------
# Group: bibtex  (extracted -> ._cli.bibtex; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.bibtex import bibtex  # noqa: E402

cli.add_command(bibtex)


# ---------------------------------------------------------------------------
# Group: pdf  (extracted -> ._cli.pdf; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.pdf import pdf  # noqa: E402

cli.add_command(pdf)


# ---------------------------------------------------------------------------
# Group: library  (extracted -> ._cli.library; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.library import (  # noqa: E402  (after `cli` is defined above)
    _do_dematerialize,
    _do_link_project_tree,
    _do_materialize,
    _library_dematerialize_options,
    _library_link_options,
    _library_materialize_options,
    library,
    library_db_audit,
    library_db_build,
    library_db_list,
    library_db_lookup,
    library_db_migrate,
)

cli.add_command(library)


# ---------------------------------------------------------------------------
# Group: mcp  (extracted -> ._cli.mcp; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.mcp import mcp  # noqa: E402

cli.add_command(mcp)


# ---------------------------------------------------------------------------
# Group: skills + list-python-apis  (extracted -> ._cli.skills)
# ---------------------------------------------------------------------------

from ._cli.skills import list_python_apis, skills  # noqa: E402

cli.add_command(skills)
cli.add_command(list_python_apis)


# ---------------------------------------------------------------------------
# Hidden deprecation aliases  (extracted -> ._cli.aliases)
# ---------------------------------------------------------------------------

from ._cli.aliases import (  # noqa: E402
    alias_db_group,
    alias_dematerialize,
    alias_highlight,
    alias_link_project_tree,
    alias_materialize,
    alias_parallel,
    alias_single,
)

cli.add_command(alias_single)
cli.add_command(alias_parallel)
cli.add_command(alias_highlight)
cli.add_command(alias_link_project_tree)
cli.add_command(alias_materialize)
cli.add_command(alias_dematerialize)
cli.add_command(alias_db_group)


# ---------------------------------------------------------------------------
# Group: auth  (extracted -> ._cli.auth; see GITIGNORED/REFACTORING.md)
# ---------------------------------------------------------------------------

from ._cli.auth import auth  # noqa: E402

cli.add_command(auth)


# ---------------------------------------------------------------------------
# Shell completion (§1a)
# ---------------------------------------------------------------------------

try:
    from scitex_dev._cli._completion import attach_shell_completion

    attach_shell_completion(cli, prog_name="scitex-scholar")
except ImportError:
    pass


# Legacy: `bibtex --bibtex …` (no subcommand) form. Click can't easily
# disambiguate that within a group, so we pre-process argv in `main()`.
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _rewrite_argv_for_bibtex_alias(argv: list[str]) -> tuple[list[str], bool]:
    """Rewrite ``bibtex --bibtex …`` (no subcommand) → ``bibtex import --bibtex …``."""
    if len(argv) < 2 or argv[0] != "bibtex":
        return argv, False
    if argv[1] in {"import", "-h", "--help"}:
        return argv, False
    return ["bibtex", "import", *argv[1:]], True


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]

    bibtex_alias_used = False
    if raw and raw[0] == "bibtex":
        raw, bibtex_alias_used = _rewrite_argv_for_bibtex_alias(raw)

    if bibtex_alias_used:
        _warn_deprecated("bibtex --bibtex …", "bibtex import --bibtex …")

    try:
        cli.main(args=raw, prog_name="scitex-scholar", standalone_mode=False)
        return 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Abort:
        click.secho("Aborted.", fg="red", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# EOF


# audit §4 — inject version into root --help
try:
    from importlib.metadata import version as _v

    cli.help = (
        f"scitex-scholar (v{_v('scitex-scholar')}) — " + (cli.help or "").lstrip()
    )
except Exception:
    pass
