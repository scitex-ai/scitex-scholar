#!/usr/bin/env python3
# File: src/scitex_scholar/_cli/_scaffolding.py

"""Click scaffolding shared by every ``_cli.<group>`` module.

This module imports nothing from ``_cli_main``, which is the whole point:
the group modules used to reach *up* into ``_cli_main`` for these names
while ``_cli_main`` imported the group modules back at its bottom, so
importing any group module first on a cold interpreter raised
``ImportError: ... partially initialized module ... (most likely due to a
circular import)``. The dependency now runs one way — group modules and
``_cli_main`` both import *down* into here.

``_cli_main`` re-exports these names for back-compat, so
``from scitex_scholar._cli_main import CONTEXT_SETTINGS`` keeps working.

Root-level command layout (``_RootGroup``, ``COMMAND_CATEGORIES``) stays in
``_cli_main``: it describes that one root group, not shared plumbing.
"""

from __future__ import annotations

import click

__all__ = [
    "CONTEXT_SETTINGS",
    "_CategorizedGroup",
    "_INT_OR_HELP",
    "_IntOrHelp",
    "_warn_deprecated",
    "spec_command_kwargs",
    "spec_group_kwargs",
]


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


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


def _warn_deprecated(old_form: str, new_form: str) -> None:
    """Emit a one-line yellow deprecation warning to stderr."""
    click.secho(
        f"DeprecationWarning: 'scitex-scholar {old_form}' is deprecated; "
        f"use 'scitex-scholar {new_form}' (will be removed in 1.4.0).",
        fg="yellow",
        err=True,
    )


# ---------------------------------------------------------------------------
# Spec-built help (audit §4b)
# ---------------------------------------------------------------------------
#
# Every CLI command/group builds its ``--help`` from a
# ``scitex_dev.ecosystem.CliHelp`` spec via ``SpecCommand`` / ``SpecGroup``
# instead of free-form text (doctrine §4: fixed-order epilog — Examples /
# Exit codes / Config resolution / See also — so help cannot drift). These
# two factories are the only construction site: each command passes its
# one-line summary plus genuine ``{prog}`` examples.
#
# ImportError fallback: scitex-dev is a hard dependency, but the floor in
# ``pyproject.toml`` predates the ``help_spec`` API, so an older scitex-dev
# degrades to plain ``help=`` text instead of breaking the CLI import.


def spec_command_kwargs(
    summary: str,
    description: tuple[str, ...] = (),
    examples: tuple[tuple[str, str], ...] = (),
    exit_codes: tuple[tuple[int, str], ...] = (),
) -> dict:
    """Decorator kwargs making a leaf a spec-built ``SpecCommand``."""
    try:
        from scitex_dev.ecosystem import CliHelp, Example, SpecCommand
    except ImportError:  # pragma: no cover — old scitex-dev without help_spec
        return {"help": "\n\n".join((summary, *description))}
    return {
        "cls": SpecCommand,
        "help_spec": CliHelp(
            summary=summary,
            description=description,
            examples=tuple(Example(cmd, note) for cmd, note in examples),
            exit_codes=exit_codes,
        ),
    }


def spec_group_kwargs(
    summary: str,
    description: tuple[str, ...] = (),
    command_categories: list[tuple[str, list[str]]] | None = None,
    cls=None,
    version_of: str | None = None,
) -> dict:
    """Decorator kwargs making a group a spec-built ``SpecGroup``.

    ``cls`` overrides the group class (e.g. a ``SpecGroup`` subclass with
    extra runtime behavior); ``command_categories`` is ignored then, since
    the subclass carries its own ``COMMAND_CATEGORIES``. ``version_of``
    names the distribution whose version renders in the summary line
    (root command only — doctrine §4).
    """
    try:
        from scitex_dev.ecosystem import CliHelp, SpecGroup
    except ImportError:  # pragma: no cover — old scitex-dev without help_spec
        return {"help": "\n\n".join((summary, *description))}
    kwargs: dict = {
        "cls": cls or SpecGroup,
        "help_spec": CliHelp(
            summary=summary, description=description, version_of=version_of
        ),
    }
    if command_categories is not None:
        kwargs["command_categories"] = command_categories
    return kwargs


# EOF
