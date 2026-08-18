#!/usr/bin/env python3
# File: src/scitex_scholar/_utils/_env.py

"""Read scitex-scholar environment variables under the fleet-prefixed name.

Every environment variable scitex-scholar OWNS is spelled
``SCITEX_SCHOLAR_<X>``. That convention is not new — the config layer
(``config/_categories/*.yaml``) already interpolates the prefixed names, and
the published skill table in ``_skills/scitex-scholar/20_env-vars.md`` already
documents them.

Several call sites never got the memo and read the bare name directly, which
made the documentation WRONG rather than merely inconsistent: a user who set
the variable scholar's own docs tell them to set got nothing, because the code
was reading a different name. `resolve_env` closes that gap without breaking
anyone who is currently relying on the legacy spelling.

Precedence is canonical-first, and the legacy read is LOUD. A silent fallback
here would be the same defect in a new place: the user would keep believing
the documented name works, and the day the legacy name is removed their setup
breaks with no warning ever having been issued.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

__all__ = ["resolve_env"]

_warned: set[str] = set()


def resolve_env(
    canonical: str,
    legacy: str | None = None,
    default: str | None = None,
) -> str | None:
    """Return the value of ``canonical``, falling back to ``legacy`` loudly.

    Parameters
    ----------
    canonical
        The ``SCITEX_SCHOLAR_*`` name. Always read first, and always wins
        when both are set — the documented name must be the one that works.
    legacy
        A pre-convention spelling still honoured for back-compat. Using it
        emits a warning naming both spellings, once per process per variable.
    default
        Returned when neither name is set.

    Returns
    -------
    str or None
        The resolved value, or ``default`` when neither variable is set.
    """
    value = os.environ.get(canonical)
    if value is not None:
        return value

    if legacy:
        legacy_value = os.environ.get(legacy)
        if legacy_value is not None:
            if legacy not in _warned:
                _warned.add(legacy)
                logger.warning(
                    "%s is deprecated and will be removed; set %s instead. "
                    "Using the value from %s for now.",
                    legacy,
                    canonical,
                    legacy,
                )
            return legacy_value

    return default


# EOF
