"""The selected-paper reader is rendered inside the existing shared pane."""
from pathlib import Path
from bs4 import BeautifulSoup
from django.template import Context, Engine


def _reader():
    root = Path(__file__).resolve().parents[4]
    text = (root / "src/scitex_scholar/_django/templates/scholar/workspace_content.html").read_text()
    start = text.index('<div class="sidebar-section hidden" data-library-hint>')
    end = text.index('<!-- Node details + graph controls:', start)
    html = Engine(libraries={"i18n": "django.templatetags.i18n"}).from_string(
        "{% load i18n %}" + text[start:end],
    ).render(Context())
    return BeautifulSoup(html, "html.parser")


def test_reader_has_explicit_empty_state_before_any_paper_is_selected():
    # Arrange
    dom = _reader()
    # Act
    state = (bool(dom.select_one('#libraryReaderEmpty').get_text(strip=True)),
             dom.select_one('#libraryReaderContent').has_attr('hidden'))
    # Assert
    assert state == (True, True)


def test_reader_labels_unknown_metadata_without_fabricated_values():
    # Arrange
    reader = _reader().select_one('#libraryPaperDetails')
    # Act
    labels = (bool(reader['data-missing']), bool(reader['data-no-abstract']))
    # Assert
    assert labels == (True, True)


def test_reader_copy_action_is_explicit_and_does_not_create_another_pane():
    # Arrange
    dom = _reader()
    # Act
    structure = (len(dom.select('button#libraryReaderCopyCitation[type=button]')),
                 len(dom.select('[data-stx-pane]')), len(dom.select('form')))
    # Assert
    assert structure == (1, 0, 0)
