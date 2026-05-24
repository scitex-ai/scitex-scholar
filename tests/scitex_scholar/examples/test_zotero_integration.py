"""Mirror of src/scitex_scholar/examples/zotero_integration.py."""
from pathlib import Path

_SRC = Path(__file__).resolve().parents[3] / "src" / "scitex_scholar" / "examples"

def test_zotero_integration_script_exists_in_examples_directory():
    # Arrange
    target = _SRC / "zotero_integration.py"
    # Act
    exists = target.is_file()
    # Assert
    assert exists, f"missing: {target}"
