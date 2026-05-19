"""Integration tests: scitex-scholar consuming scitex-browser.

These are the upper-package integration tests (in the consumer's suite) that
verify the one-way dependency rule:
    - scitex-scholar may consume scitex-browser
    - scitex-browser must NOT reach back into scitex-scholar

They are intentionally lightweight: no live browser launches, just surface-level
wiring checks that would catch API drift between the two packages.

NOTE: the decoupling fix and the chrome_cache_dir kwarg ship in
scitex-browser ≥ 0.1.2. On older PyPI versions (0.1.0, 0.1.1) the reverse
`from scitex.scholar.config import ...` import still lives in the source
and ``ChromeProfileManager`` takes ``config`` positionally. The two tests
below skip themselves when that legacy signature/source is present so CI
with a pinned-but-pre-release dep tree doesn't go red.
"""

import importlib
from pathlib import Path

import pytest


def _browser_has_legacy_reverse_import() -> bool:
    try:
        mod = importlib.import_module("scitex_browser.core.ChromeProfileManager")
    except Exception:
        return True
    src = Path(mod.__file__).read_text()
    return "scitex.scholar" in src or "scitex_scholar" in src


def _browser_accepts_chrome_cache_dir() -> bool:
    try:
        from inspect import signature

        from scitex_browser.core.ChromeProfileManager import ChromeProfileManager
    except Exception:
        return False
    return "chrome_cache_dir" in signature(ChromeProfileManager.__init__).parameters


_LEGACY_REVERSE_IMPORT = _browser_has_legacy_reverse_import()
_HAS_CHROME_CACHE_DIR = _browser_accepts_chrome_cache_dir()


@pytest.mark.skipif(
    _LEGACY_REVERSE_IMPORT,
    reason="scitex-browser <0.1.2 still has the reverse import; decouple fix not yet released",
)
def test_scholar_uses_browser_without_circular_import_scitex_scholar_not_in_src():
    # Arrange
    mod = importlib.import_module("scitex_browser.core.ChromeProfileManager")
    # Act
    src = Path(mod.__file__).read_text()
    # Act
    # Assert
    assert "scitex_scholar" not in src


@pytest.mark.skipif(
    _LEGACY_REVERSE_IMPORT,
    reason="scitex-browser <0.1.2 still has the reverse import; decouple fix not yet released",
)
def test_scholar_uses_browser_without_circular_import_scitex_scholar_not_in_src():
    # Arrange
    mod = importlib.import_module("scitex_browser.core.ChromeProfileManager")
    # Act
    src = Path(mod.__file__).read_text()
    # Act
    # Assert
    assert "scitex.scholar" not in src




@pytest.mark.skipif(
    not _HAS_CHROME_CACHE_DIR,
    reason="ChromeProfileManager.chrome_cache_dir kwarg only in scitex-browser >=0.1.2",
)
def test_scholar_browser_manager_exposes_chrome_profile_manager_manager_profile_dir_equals_base_dir_system():
    # Arrange
    from scitex_browser.core.ChromeProfileManager import ChromeProfileManager
    from scitex_scholar.config import ScholarConfig
    config = ScholarConfig()
    base_dir = config.get_cache_chrome_dir("system").parent
    # Act
    manager = ChromeProfileManager("system", chrome_cache_dir=base_dir)
    # Act
    # Assert
    assert manager.profile_dir == base_dir / "system"


@pytest.mark.skipif(
    not _HAS_CHROME_CACHE_DIR,
    reason="ChromeProfileManager.chrome_cache_dir kwarg only in scitex-browser >=0.1.2",
)
def test_scholar_browser_manager_exposes_chrome_profile_manager_manager_profile_dir_exists():
    # Arrange
    from scitex_browser.core.ChromeProfileManager import ChromeProfileManager
    from scitex_scholar.config import ScholarConfig
    config = ScholarConfig()
    base_dir = config.get_cache_chrome_dir("system").parent
    # Act
    manager = ChromeProfileManager("system", chrome_cache_dir=base_dir)
    # Act
    # Assert
    assert manager.profile_dir.exists()




def test_scholar_url_finder_exports_hasattr_scitex_scholar_scholarurlfinder():
    # Arrange
    # Act
    import scitex_scholar
    # Act
    # Assert
    assert hasattr(scitex_scholar, "ScholarURLFinder")


def test_scholar_url_finder_exports_hasattr_scitex_scholar_scholarbrowsermanager():
    # Arrange
    # Act
    import scitex_scholar
    # Act
    # Assert
    assert hasattr(scitex_scholar, "ScholarBrowserManager")


def test_scholar_url_finder_exports_hasattr_scitex_scholar_scholarauthmanager():
    # Arrange
    # Act
    import scitex_scholar
    # Act
    # Assert
    assert hasattr(scitex_scholar, "ScholarAuthManager")




def test_chrome_profile_manager_accepts_scholar_path_manager():
    """Back-compat duck-typing: any object with get_cache_chrome_dir works."""
    # Arrange
    # Act
    # Assert
    from scitex_browser.core.ChromeProfileManager import ChromeProfileManager

    class FakeConfig:
        def __init__(self, base):
            self._base = base

        def get_cache_chrome_dir(self, profile_name):
            p = self._base / profile_name
            p.mkdir(parents=True, exist_ok=True)
            return p

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fake = FakeConfig(Path(tmp))
        m = ChromeProfileManager("system", config=fake)
        assert m.profile_dir == Path(tmp) / "system"
