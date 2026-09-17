#!/usr/bin/env python3
"""Generate src/scitex_scholar/_django/locale/ja/LC_MESSAGES/django.po for Scholar i18n.

Extracts the msgids exactly as Django's i18n machinery looks them up at RUNTIME:
  - {% trans "X" %}  -> the literal X
  - {% blocktrans %}...{% endblocktrans %}  -> the RAW block text, verbatim
    (newlines and indentation preserved, tags and entities as-is). Django does
    NOT collapse whitespace unless the template says "blocktrans trimmed".
    Keying the .po on anything other than the exact raw string makes gettext
    fall back to the msgid (English) at runtime — a silent mixed-language page.
  - the gettext values in views._js_i18n_dict (the JS-only string dict).

Then applies the JA translation table and compiles the .mo via babel (msgfmt is
not on PATH in this container).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src/scitex_scholar/_django/templates/scholar/scholar.html"
VIEWS = ROOT / "src/scitex_scholar/_django/views.py"
LOCALE_DIR = ROOT / "src/scitex_scholar/_django/locale/ja/LC_MESSAGES"


def single_line_trans_ids() -> list:
    t = TEMPLATE.read_text()
    t = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", t, flags=re.S)
    return [m.group(1) for m in re.finditer(r'\{%\s*trans\s+"([^"]+)"\s*%\}', t)]


# The three {% blocktrans %} messages, keyed on the EXACT raw block text Django
# passes to gettext at runtime (verified by instrumenting gettext on a live
# render). Newlines/indentation are literal.
BLOCKTRANS_MSGIDS = [
    "Search academic databases (OpenAlex, Crossref, PubMed,\n"
    "                                    Semantic Scholar, &#8230;) by keyword. This searches\n"
    "                                    <strong>external databases</strong>, not your Library\n"
    "                                    (a separate tab).",
    "Query syntax:\n"
    "                                            <code>-word</code> excludes a term,\n"
    "                                            <code>year:2020-2024</code> bounds the\n"
    "                                            publication year,\n"
    "                                            <code>if:&gt;5</code> filters by impact factor.",
    "Your papers, stored locally. Use <strong>Enrich</strong>\n"
    "                                    to fill in metadata (abstract, citations, impact\n"
    "                                    factor) from the databases, or\n"
    "                                    <strong>Import</strong> BibTeX and\n"
    "                                    <strong>Export</strong> your library.",
]


def views_msgids() -> list:
    v = VIEWS.read_text()
    m = re.search(r"def _js_i18n_dict\(\)[\s\S]*?\n    \}\n", v)
    body = m.group(0) if m else ""
    return [mm.group(1) for mm in re.finditer(r'_i18n\(\s*"([^"]+)"', body)]


JA = {
    # --- Header / shell ---
    "SciTeX Scholar": "SciTeX Scholar",
    "Scientific Literature Management": "科学文献管理",
    # --- Sidebar ---
    "Service Status": "サービス状態",
    "Checking...": "確認中…",
    "Graph Controls": "グラフ操作",
    "Scroll": "スクロール", "Zoom": "ズーム", "Drag": "ドラッグ", "Pan": "パン",
    "Click": "クリック", "Select node": "ノードを選択",
    # --- Tabs ---
    "Search databases": "データベースを検索",
    "Library": "ライブラリ",
    "Citation Graph": "引用グラフ",
    # --- Search tab ---
    "Search Papers": "論文を検索",
    BLOCKTRANS_MSGIDS[0]: (
        "キーワードで学術データベース（OpenAlex、Crossref、PubMed、Semantic Scholar など）を検索します。"
        "これは<strong>外部データベース</strong>を検索するもので、ライブラリ（別のタブ）ではありません。"
    ),
    "Query": "クエリ",
    "Results": "結果",
    "Advanced": "詳細",
    BLOCKTRANS_MSGIDS[1]: (
        "クエリ構文：<code>-word</code> で用語を除外、<code>year:2020-2024</code> で発行年を指定、"
        "<code>if:&gt;5</code> でインパクトファクターで絞り込みます。"
    ),
    "Search source": "検索ソース",
    "All sources (parallel)": "すべてのソース（並列）",
    "Single source": "単一ソース",
    "Ignore cache": "キャッシュを無視",
    "CrossRef API": "CrossRef API",
    "Configured": "設定済み",
    "Not configured": "未設定",
    "Searching databases... This may take a moment.": "データベースを検索中。少し時間がかかる場合があります。",
    "An error occurred": "エラーが発生しました",
    "Dismiss": "閉じる",
    # --- Library tab ---
    BLOCKTRANS_MSGIDS[2]: (
        "ローカルに保存された論文です。<strong>補完</strong> でデータベースからメタデータ"
        "（抄録、被引用数、インパクトファクター）を入力するか、<strong>インポート</strong> で "
        "BibTeX をインポートしてライブラリを<strong>エクスポート</strong>できます。"
    ),
    "Export": "エクスポート",
    "BibTeX (.bib)": "BibTeX (.bib)",
    "RIS (.ris)": "RIS (.ris)",
    "EndNote (.enw)": "EndNote (.enw)",
    "Import BibTeX": "BibTeX をインポート",
    "Loading your library...": "ライブラリを読み込み中…",
    # --- Graph tab ---
    "Build Citation Network": "引用ネットワークを構築",
    "Enter a DOI to build an interactive citation network. The graph shows related papers based on bibliographic coupling, co-citation, and direct citations.":
        "DOI を入力すると対話的な引用ネットワークを構築します。グラフは書誌的結合、共被引用、直接引用に基づいた関連論文を表示します。",
    "DOI": "DOI",
    "Build Graph": "グラフを構築",
    "Papers": "論文",
    "Building citation network... This may take a moment.": "引用ネットワークを構築中。少し時間がかかる場合があります。",
    "Citation Network": "引用ネットワーク",
    "Fit to view": "画面に合わせる",
    "Reset zoom": "ズームをリセット",
    "Download SVG": "SVG をダウンロード",
    "Related Papers": "関連論文",
    # --- JS dict (views._js_i18n_dict) ---
    "Build citation graph": "引用グラフを構築",
    "Enrich": "補完",
    "Unknown authors": "著者不明",
    "Untitled": "無題",
    "Service available": "サービス利用可能",
    "Service limited": "サービス制限あり",
    "Service unavailable": "サービス利用不可",
    "Not checked yet": "未確認",
    "Unknown": "不明",
    "Related papers": "関連論文",
    "Paper": "論文",
    "char abstract": "文字の抄録",
    "citations": "被引用",
    "Enriched: %(parts)s": "補完済み：%(parts)s",
    "Enriching…": "補完中…",
    "Enrichment failed": "補完に失敗",
    "Enrichment failed (HTTP %(status)s)": "補完に失敗（HTTP %(status)s）",
    "Your library is empty. Save papers from Search or Import, then Enrich them here.":
        "ライブラリは空です。検索から論文を保存するかインポートし、ここで補完してください。",
    "Imported %(n)s paper from %(file)s": "%(file)s から %(n)s 件の論文をインポートしました",
    "Imported %(n)s papers from %(file)s": "%(file)s から %(n)s 件の論文をインポートしました",
}


def q(s: str) -> str:
    """A .po string literal: double-quoted, with backslash, double-quote, and
    newline escaped. (A raw newline inside a quoted .po string would be an
    implicit concatenation / format error, so it must become \\n.)"""
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + out + '"'


def main() -> None:
    ids = list(dict.fromkeys(single_line_trans_ids() + BLOCKTRANS_MSGIDS + views_msgids()))
    missing = [i for i in ids if i not in JA]
    if missing:
        print("WARNING: no JA translation for:")
        for m in missing:
            print("   ", repr(m))
    LOCALE_DIR.mkdir(parents=True, exist_ok=True)
    po = LOCALE_DIR / "django.po"
    lines = [
        "# Scholar JA translations (operator directive 2026-09-14: EN default, full JA).",
        "# English is the source; these JA translations are drafted by scitex-scholar",
        "# and will be reviewed. msgids match Django's runtime gettext lookup exactly:",
        "# {% trans %} literals verbatim; {% blocktrans %} RAW block text (newlines kept).",
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: scitex-scholar\\n"',
        '"Language: ja\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"PO-Revision-Date: 2026-09-14 00:00+0900\\n"',
        '"Last-Translator: scitex-scholar <agent@scitex.ai>\\n"',
        "",
    ]
    for i in ids:
        lines.append(f"msgid {q(i)}")
        lines.append(f"msgstr {q(JA.get(i, i))}")
        lines.append("")
    po.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {po} with {len(ids)} msgids")
    # compile via babel (msgfmt is not on PATH in this container)
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po
    with open(po, "rb") as f:
        cat = read_po(f)
    with open(LOCALE_DIR / "django.mo", "wb") as f:
        write_mo(f, cat)
    print("compiled django.mo OK")


if __name__ == "__main__":
    main()
