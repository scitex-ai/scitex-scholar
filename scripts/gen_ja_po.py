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
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# scholar.html is the shell (no {% trans %} of its own); the user-facing copy
# lives in workspace_content.html, included via workspace_renderer.html.
# Scanning only scholar.html silently drops every template msgid on regen
# (operator i18n fix 2026-10-16: regen produced an EN-only JA page).
TEMPLATES = [
    ROOT / "src/scitex_scholar/_django/templates/scholar/scholar.html",
    ROOT / "src/scitex_scholar/_django/templates/scholar/workspace_content.html",
]
VIEWS = ROOT / "src/scitex_scholar/_django/views.py"
LOCALE_DIR = ROOT / "src/scitex_scholar/_django/locale/ja/LC_MESSAGES"


def single_line_trans_ids() -> list:
    t = "\n".join(path.read_text() for path in TEMPLATES)
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
    # Every _i18n("...") msgid in views.py: the JS dict AND the graph_health /
    # _not_configured_payload / _degraded_payload bodies, whose error/detail/
    # fix render as the Service Status sidebar paragraph. AST evaluation
    # resolves implicit concatenation, so the msgid matches the runtime string
    # however views.py wraps the literal; a first-chunk regex would silently
    # key the catalog wrong and fall back to English at runtime.
    tree = ast.parse(VIEWS.read_text())
    ids = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_i18n"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            ids.append(node.args[0].value)
    return ids


JA = {
    # --- Header / shell ---
    "SciTeX Scholar": "SciTeX Scholar",
    "Scientific Literature Management": "科学文献管理",
    # --- Sidebar ---
    "Service Status": "サービス状態",
    "Collapse status panel": "ステータスパネルを折りたたむ",
    "Expand status panel": "ステータスパネルを展開する",
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
    "Filter your library": "ライブラリを絞り込む",
    "Title, author, or DOI": "タイトル、著者、DOI",
    "Clear filters": "絞り込みを解除",
    "Loading your library...": "ライブラリを読み込み中…",
    # --- Graph tab slice 3a strings: these shipped in the committed .po
    # with translations but were never entered in this table, so a regen
    # silently reset them to English (caught by
    # test_ja_catalog_translates_every_msgid). Entering them here makes
    # the script the source of truth again.
    "Seed from your Library": "ライブラリからシードを選択",
    "Loading your library…": "ライブラリを読み込み中…",
    "How It Works": "使い方",
    "Bibliographic Coupling": "書誌結合",
    "Papers sharing common references": "共通の参考文献を持つ論文",
    "Co-citation": "共引用",
    "Papers frequently cited together": "共に引用されることの多い論文",
    "Direct Citations": "直接引用",
    "Papers citing or cited by the seed": "シード論文を引用または被引用する論文",
    "No papers with a DOI in your library yet.": "ライブラリにはDOI付きの論文がまだありません。",
    # --- Library tab slice 3b (old-direct parity: Zotero/CP reflection) ---
    "Zotero": "Zotero",
    "Import from your local Zotero database, or download the library as BibTeX for Zotero.":
        "ローカルの Zotero データベースからインポートするか、ライブラリを Zotero 用の BibTeX としてダウンロードできます。",
    "Import source": "インポート元",
    "All papers": "すべての論文",
    "By collection": "コレクション別",
    "By tags": "タグ別",
    "Tags, comma-separated": "タグ（カンマ区切り）",
    "Import from Zotero": "Zotero からインポート",
    "Download BibTeX for Zotero": "Zotero 用に BibTeX をダウンロード",
    "Connected Papers": "Connected Papers",
    "Import a Connected Papers graph by seed paper.":
        "起点論文から Connected Papers のグラフをインポートします。",
    "Find paper IDs at semanticscholar.org":
        "論文 ID は semanticscholar.org で確認できます",
    "Semantic Scholar paper ID": "Semantic Scholar 論文 ID",
    "40-char SHA or DOI": "40文字の SHA または DOI",
    "Import Graph": "グラフをインポート",
    # --- Graph tab ---
    "Build Citation Network": "引用ネットワークを構築",
    # Graph seed/limit copy added with the graph demotion; these were missing
    # from the catalog, so the JA page rendered them in English.
    "Start with a DOI. Find one by title, topic, or keywords in Search or your Library, then build an interactive citation graph of related papers.":
        "DOI から始めます。タイトル・トピック・キーワードで検索タブまたはライブラリから DOI を探し、関連論文の対話的な引用グラフを構築してください。",
    "Paste the DOI for one seed paper; titles and keywords belong in Search.":
        "起点となる論文の DOI を貼り付けてください。タイトルやキーワードでの検索は検索タブで行います。",
    "Max papers in graph": "グラフ内の最大論文数",
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
    # --- Search tab slice 2 (old-direct parity: sorter/filter/bulk) ---
    "Details": "詳細",
    "Sort by": "並び替え",
    "Relevance": "関連度順",
    "Year (newest)": "発行年（新しい順）",
    "Year (oldest)": "発行年（古い順）",
    "Title (A-Z)": "タイトル（A-Z順）",
    "Source": "ソース",
    "All sources": "すべてのソース",
    "Select all": "すべて選択",
    "Save selected": "選択を保存",
    "Save & enrich": "保存して補完",
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
    "Your library is empty. Import a BibTeX file to add papers.":
        "ライブラリは空です。BibTeX ファイルをインポートして論文を追加してください。",
    "No papers match the current filters.": "現在の絞り込み条件に一致する論文はありません。",
    "%(count)s of %(total)s Papers": "%(total)s 件中 %(count)s 件の論文",
    "No papers matched this query.": "このクエリに一致する論文はありませんでした。",
    "Local corpus (NAS)": "ローカルコーパス（NAS）",
    "Online fallback": "オンラインへのフォールバック",
    "Imported %(n)s paper from %(file)s": "%(file)s から %(n)s 件の論文をインポートしました",
    "Imported %(n)s papers from %(file)s": "%(file)s から %(n)s 件の論文をインポートしました",
    "Save": "保存",
    "Saving…": "保存中…",
    "Saved": "保存済み",
    "Save failed": "保存に失敗",
    "Select results to save.": "保存する結果を選択してください。",
    "Saved %(saved)s of %(total)s": "%(total)s 件中 %(saved)s 件を保存",
    "Enriched %(done)s of %(total)s": "%(total)s 件中 %(done)s 件を補完",
    # --- JS dict, slice 3b (Zotero / Connected Papers import controls) ---
    "Importing…": "インポート中…",
    "Import failed": "インポートに失敗",
    "Zotero database found": "Zotero データベースが見つかりました",
    "Zotero database not found": "Zotero データベースが見つかりません",
    "Connected Papers available": "Connected Papers 利用可能",
    "Connected Papers unavailable": "Connected Papers 利用不可",
    "Imported %(imported)s of %(total)s papers":
        "%(total)s 件中 %(imported)s 件の論文をインポートしました",
    "Enter a Semantic Scholar paper ID":
        "Semantic Scholar の論文 ID を入力してください",
    # --- JS dict, slice 3c (project-sync controls) ---
    "Project": "プロジェクト",
    "All projects": "すべてのプロジェクト",
    "Project: %(project)s": "プロジェクト: %(project)s",
    # --- Service Status sidebar paragraph (graph_health / _not_configured_payload /
    # _degraded_payload error+detail+fix; operator screenshot 2026-10-16) ---
    "CrossRef API not configured": "CrossRef API 未設定",
    "The citation graph reads its data from a crossref-local HTTP API; scholar never opens the corpus files itself. No endpoint is configured, so there is nothing to query.":
        "引用グラフは crossref-local HTTP API からデータを取得します。scholar がコーパスファイルを直接開くことはありません。エンドポイントが設定されていないため、問い合わせ先がありません。",
    "Set %(setting)s to a running crossref-local endpoint (env var of the same name, or the Django setting when scholar is mounted in a host project), then restart the server. Installing the `crossref-local` package supplies a default endpoint, which scholar falls back to when the variable is unset.":
        "%(setting)s に稼働中の crossref-local エンドポイントを設定し（ホストプロジェクトにマウントしている場合は同名の環境変数または Django 設定）、サーバーを再起動してください。`crossref-local` パッケージをインストールするとデフォルトのエンドポイントが用意され、変数が未設定の場合はそちらにフォールバックします。",
    "Citation Graph: not checked": "引用グラフ：未確認",
    "A crossref-local endpoint is configured. The graph backend is probed when you open the Citation Graph tab, so a slow or unreachable backend cannot delay the rest of the page.":
        "crossref-local エンドポイントが設定されています。グラフバックエンドの確認は引用グラフタブを開いたときに行われるため、応答の遅いバックエンドや到達不能なバックエンドがページの他の表示を遅らせることはありません。",
    "Open the Citation Graph tab to check it.":
        "引用グラフタブを開いて確認してください。",
    "Citation Graph: unavailable": "引用グラフ：利用不可",
    "The crossref-local endpoint is configured but could not be reached right now, so citation graphs cannot be built.":
        "crossref-local エンドポイントは設定されていますが、現在到達できないため、引用グラフを構築できません。",
    "Verify the crossref-local service is running and that the endpoint is reachable, then retry.":
        "crossref-local サービスが稼働していることと、エンドポイントに到達できることを確認してから、再試行してください。",
    "Citation Graph: limited": "引用グラフ：制限あり",
    "The crossref-local endpoint is configured and reachable, but the probe returned no data for the canary paper. Citation graphs may be incomplete.":
        "crossref-local エンドポイントは設定され到達可能ですが、確認用の論文に対するプローブがデータを返さなかったため、引用グラフが不完全な場合があります。",
    "Check that the crossref-local endpoint is serving the corpus you expect; the citation graph depends on it.":
        "crossref-local エンドポイントが想定どおりのコーパスを提供しているか確認してください。引用グラフはこのエンドポイントに依存しています。",
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
