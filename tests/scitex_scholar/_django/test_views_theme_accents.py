#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Navy/gold accent re-map (operator hue decision 2026-10-20).

Monotone + navy CTA in light mode / gold CTA in dark mode. The base
`--accent` comes from the SDK theme (navy/gold); the leaf owned two
green hover values + one dormant bright-blue fallback. VERIFY: pins.
"""

from __future__ import annotations

from pathlib import Path as _Path

from scitex_scholar._django import views as _views

_CSS = (
    _Path(_views.__file__).parent / "static" / "scholar" / "css" / "_partials"
)


def test_accent_hover_is_navy_gold_not_green():
    # Arrange
    base = (_CSS / "_base.css").read_text()
    # Act (no Act step: static text inspection)
    # Assert -- light navy-darkened, dark gold-darkened; no green hover.
    assert (
        "--accent-hover: #0f1e33" in base
        and "--accent-hover: #b98d5f" in base
        and "#059669" not in base
        and "#047857" not in base
    )


def test_accent_fallback_is_navy_not_bright_blue():
    # Arrange
    lib = (_CSS / "_library.css").read_text()
    # Act (no Act step: static text inspection)
    # Assert -- dormant fallback matches the navy base, never sky blue.
    assert ("var(--accent, #1a2a40)" in lib) and ("#1f6feb" not in lib)
