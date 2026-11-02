"""Exercise the shipped frontend sorter in the declared CI Node runtime."""
from pathlib import Path
import subprocess


def test_loaded_search_sorting_preserves_identity_and_missing_values():
    # Arrange
    root = Path(__file__).resolve().parents[3]
    script = root / "tests/integration/scholar/_django/search_order.cjs"
    helper = root / "src/scitex_scholar/_django/static/scholar/js/search-order.js"
    # Act
    result = subprocess.run(
        ["node", str(script), str(helper)], capture_output=True, text=True, timeout=10,
    )
    # Assert
    assert result.returncode == 0, result.stdout + result.stderr
