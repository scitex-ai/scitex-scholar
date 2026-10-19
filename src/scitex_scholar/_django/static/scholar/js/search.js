/**
 * Scholar GUI - Search tab
 *
 * Submits the query to /api/search and renders the results. All search
 * logic (query parsing, engine selection, ranking) belongs to the package's
 * ScholarSearchEngine behind that endpoint -- this file only renders.
 *
 * COMPASS 2026-09-10 (L653, L345): the Advanced block (query syntax, search
 * source, Ignore-cache, CrossRef status) is collapsed by default. The
 * search source and the "Ignore cache" checkbox are wired into the request
 * here (mode + no_cache are existing /api/search params). Each result with a
 * DOI offers "Build citation graph", which prefills the Graph tab's DOI and
 * jumps there -- graph creation from a search result, the demotion path.
 *
 * SLICE 2 (old-direct parity, CCT4130 slice-1): sorter + source filter +
 * bulk/pipeline pills over the results. Sort/filter re-render the cached
 * result set locally (no refetch); the pills POST to the EXISTING library
 * save/save-bulk/enrich endpoints -- search adds no backend of its own.
 * Selection is keyed by DOI-or-title so it survives re-sorts.
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("searchForm");
  if (!form) return;

  const input = document.getElementById("searchInput");
  const maxResults = document.getElementById("searchMaxResults");
  const modeSelect = document.getElementById("searchMode");
  const sourcesGrid = document.getElementById("searchSourcesGrid");
  // Slice 2 (old-direct unification): the Filters number inputs. Empty
  // means unbounded; non-empty values travel under the hub param names.
  const filterInputs = {
    year_from: document.getElementById("searchYearFrom"),
    year_to: document.getElementById("searchYearTo"),
    min_citations: document.getElementById("searchMinCitations"),
    max_citations: document.getElementById("searchMaxCitations"),
    min_impact_factor: document.getElementById("searchMinImpact"),
    max_impact_factor: document.getElementById("searchMaxImpact"),
  };
  const noCache = document.getElementById("searchNoCache");
  const loading = document.getElementById("searchLoading");
  const errorBox = document.getElementById("searchError");
  const errorMessage = document.getElementById("searchErrorMessage");
  const retryBtn = document.getElementById("searchRetryBtn");
  const results = document.getElementById("searchResults");
  const resultsContent = document.getElementById("searchResultsContent");
  const stats = document.getElementById("searchStats");
  const sortSelect = document.getElementById("searchSort");
  const sourceFilter = document.getElementById("searchSourceFilter");
  const selectAll = document.getElementById("searchSelectAll");
  const saveSelectedBtn = document.getElementById("searchSaveSelected");
  const enrichSelectedBtn = document.getElementById("searchEnrichSelected");
  const bulkStatus = document.getElementById("searchBulkStatus");
  // Slice 11 (old-direct unification): PDFs bulk pill -- hub downloads
  // OA PDFs for the checked rows.
  const downloadPdfsBtn = document.getElementById("searchDownloadPdfs");
  // Slice 3 (old-direct unification): the results-header tools -- abstract
  // truncated/full toggle, open-selected-URLs, export-selected-BibTeX.
  const abstractToggle = document.getElementById("searchAbstractToggle");
  const openUrlsBtn = document.getElementById("searchOpenUrls");
  const exportBibtexBtn = document.getElementById("searchExportBibtex");
  let abstractFull = false;
  const ABSTRACT_TRUNCATE_AT = 300;

  // The last fetched result set (engine order = relevance) plus the user's
  // selection, keyed by DOI-or-title so re-sorts keep the checked rows.
  let lastPapers = [];
  const selected = new Set();

  // Enrichment fans one request per paper; cap the pipeline pill so one
  // click cannot queue hundreds of sequential enrichment runs.
  const ENRICH_LIMIT = 20;

  const show = (el) => el && el.classList.remove("hidden");
  const hide = (el) => el && el.classList.add("hidden");

  // Error fallback (UX standard): the error box retries the operation that
  // failed, not just dismisses it. Each failure site passes its own retry;
  // validation messages pass none, so the retry button stays hidden for
  // mistakes the user must fix by hand (empty query).
  let retryAction = null;

  function showError(message, retry) {
    errorMessage.textContent = message;
    retryAction = typeof retry === "function" ? retry : null;
    if (retryBtn) retryBtn.classList.toggle("hidden", !retryAction);
    show(errorBox);
  }

  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      if (!retryAction) return;
      hide(errorBox);
      retryAction();
    });
  }

  // CSRF: same pattern as library.js -- the mounted hub enables
  // CsrfViewMiddleware; standalone has no token and needs no header.
  function csrfHeaders(extra) {
    const headers = Object.assign({}, extra);
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const csrf = csrfInput ? csrfInput.value : "";
    if (csrf) headers["X-CSRFToken"] = csrf;
    return headers;
  }

  function paperKey(paper, index) {
    if (paper.doi) return `doi:${paper.doi}`;
    if (paper.title) return `title:${paper.title}`;
    return `index:${index}`;
  }

  function formatAuthors(paper) {
    const authors = paper.authors || [];
    if (!authors.length) return scholarT("Unknown authors");
    const names = authors.map((a) =>
      typeof a === "string" ? a : a.name || "",
    );
    return names.length > 3
      ? `${names.slice(0, 3).join(", ")} et al.`
      : names.join(", ");
  }

  /**
   * Jump to the Citation Graph tab with this paper's DOI prefilled.
   * Does NOT auto-submit -- the user still presses "Build Graph", so the
   * action stays explicit rather than surprising.
   */
  function buildGraphFromDoi(doi) {
    const doiInput = document.getElementById("doiInput");
    if (doiInput && doi) {
      doiInput.value = doi;
    }
    const graphTab = document.querySelector(
      '.stx-content-tabs__tab[aria-controls="tab-graph"]',
    );
    if (graphTab) graphTab.click();
    if (doiInput) doiInput.focus();
  }

  // The flat shape library_save accepts (same rows library_list returns).
  // Project sync (parity slice 3c): saves file into the header picker's
  // ?project= selection, mirroring hub old-direct's per-save project
  // filing. Absent selection stays user-scoped (project: undefined is
  // dropped by JSON.stringify, so the backend sees no project key).
  function currentProject() {
    try {
      return new URLSearchParams(window.location.search).get("project") || undefined;
    } catch (e) {
      return undefined;
    }
  }

  function savePayload(paper) {
    return {
      title: paper.title || "",
      authors: paper.authors || [],
      year: paper.year || null,
      doi: paper.doi || "",
      abstract: paper.abstract || "",
      venue: paper.venue || paper.journal || "",
      citation_count: paper.citation_count || null,
      project: currentProject(),
    };
  }

  async function saveOne(paper) {
    const resp = await fetch(`${STX_MOUNT}/api/library/save`, {
      method: "POST",
      headers: csrfHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(savePayload(paper)),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || scholarT("Save failed"));
    return data.library_id;
  }

  function renderPaper(paper, index) {
    const item = document.createElement("div");
    item.className = "search-result";

    const row = document.createElement("div");
    row.className = "search-result__row";

    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "search-result__select";
    check.checked = selected.has(paperKey(paper, index));
    check.setAttribute("aria-label", scholarT("Save"));
    check.addEventListener("change", () => {
      const key = paperKey(paper, index);
      if (check.checked) selected.add(key);
      else selected.delete(key);
      syncSelectAll();
    });
    row.appendChild(check);

    const body = document.createElement("div");
    body.className = "search-result__body";

    const title = document.createElement("div");
    title.className = "search-result__title";
    // textContent, not innerHTML: titles and abstracts are third-party data.
    title.textContent = paper.title || scholarT("Untitled");
    body.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "search-result__meta";
    const bits = [formatAuthors(paper)];
    if (paper.year) bits.push(String(paper.year));
    if (paper.journal) bits.push(paper.journal);
    if (paper.source) bits.push(paper.source);
    bits.forEach((text) => {
      const span = document.createElement("span");
      span.textContent = text;
      meta.appendChild(span);
    });
    body.appendChild(meta);

    // DOI line: the DOI link plus a "Build citation graph" action.
    if (paper.doi) {
      const doiLine = document.createElement("div");
      doiLine.className = "search-result__meta";

      const link = document.createElement("a");
      link.href = `https://doi.org/${paper.doi}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = paper.doi;
      doiLine.appendChild(link);

      const graphBtn = document.createElement("button");
      graphBtn.type = "button";
      graphBtn.className = "search-result__graph-btn";
      graphBtn.textContent = scholarT("Build citation graph");
      graphBtn.addEventListener("click", () => buildGraphFromDoi(paper.doi));
      doiLine.appendChild(graphBtn);

      body.appendChild(doiLine);
    }

    if (paper.abstract) {
      const abstract = document.createElement("div");
      abstract.className = "search-result__abstract";
      // The full text rides the DOM so the header toggle flips length
      // without a refetch; textContent keeps third-party data inert.
      abstract.dataset.full = paper.abstract;
      abstract.textContent = abstractText(paper.abstract);
      body.appendChild(abstract);
    }

    // Per-result actions: Save to the library (slice-4 backend on the
    // search surface) beside the graph demotion path.
    const actions = document.createElement("div");
    actions.className = "search-result__actions";
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "search-result__save-btn";
    saveBtn.textContent = scholarT("Save");
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = scholarT("Saving…");
      try {
        await saveOne(paper);
        saveBtn.textContent = scholarT("Saved");
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.textContent = scholarT("Save");
        showError(`${scholarT("Save failed")}: ${err.message}`, () => saveBtn.click());
      }
    });
    actions.appendChild(saveBtn);
    body.appendChild(actions);

    row.appendChild(body);
    item.appendChild(row);
    return item;
  }

  function viewPapers() {
    const source = sourceFilter ? sourceFilter.value : "";
    const order = sortSelect ? sortSelect.value : "relevance";
    let papers = lastPapers.map((paper, index) => ({ paper, index }));
    if (source) {
      papers = papers.filter(({ paper }) => (paper.source || "") === source);
    }
    if (order === "year-desc" || order === "year-asc") {
      const dir = order === "year-desc" ? -1 : 1;
      papers = papers
        .slice()
        .sort((a, b) => ((a.paper.year || 0) - (b.paper.year || 0)) * dir);
    } else if (order === "title") {
      papers = papers
        .slice()
        .sort((a, b) =>
          String(a.paper.title || "").localeCompare(String(b.paper.title || "")),
        );
    }
    return papers;
  }

  function refreshSourceOptions() {
    if (!sourceFilter) return;
    const current = sourceFilter.value;
    // Capture the server-translated "All sources" label BEFORE replacing
    // the options -- after replaceChildren the static option is gone.
    const staticAll = sourceFilter.querySelector('option[value=""]');
    const allLabel =
      staticAll && staticAll.textContent ? staticAll.textContent : "All sources";
    const sources = [];
    lastPapers.forEach((paper) => {
      const source = paper.source || "";
      if (source && !sources.includes(source)) sources.push(source);
    });
    sourceFilter.replaceChildren();
    const all = document.createElement("option");
    all.value = "";
    // The static "All sources" option is translated server-side; the
    // per-source options are corpus proper nouns and stay as-is.
    all.textContent = allLabel;
    sourceFilter.appendChild(all);
    sources.forEach((source) => {
      const option = document.createElement("option");
      option.value = source;
      option.textContent = source;
      sourceFilter.appendChild(option);
    });
    sourceFilter.value = sources.includes(current) ? current : "";
  }

  function syncSelectAll() {
    if (!selectAll) return;
    const visible = viewPapers().map(({ paper, index }) =>
      paperKey(paper, index),
    );
    selectAll.checked =
      visible.length > 0 && visible.every((key) => selected.has(key));
  }

  // Slice 3: abstract length follows the header toggle (default truncated,
  // the pre-slice rendering, so nothing changes until the user flips it).
  function abstractText(full) {
    if (abstractFull || full.length <= ABSTRACT_TRUNCATE_AT) return full;
    return `${full.slice(0, ABSTRACT_TRUNCATE_AT)}...`;
  }

  function applyAbstractMode() {
    document.querySelectorAll(".search-result__abstract").forEach((el) => {
      el.textContent = abstractText(el.dataset.full || "");
    });
    if (abstractToggle) {
      abstractToggle.textContent = abstractFull
        ? scholarT("Abstract: full")
        : scholarT("Abstract: truncated");
      abstractToggle.dataset.mode = abstractFull ? "full" : "truncated";
    }
  }

  // Slice 3: client-side BibTeX for the checked rows (hub parity: generated
  // in-browser, Blob download, no backend round-trip).
  function bibtexEscape(value) {
    return String(value || "")
      .replace(/\\/g, "\\\\")
      .replace(/([{}])/g, "\\$1");
  }

  function bibtexAuthors(paper) {
    const authors = paper.authors || [];
    return authors
      .map((a) => (typeof a === "string" ? a : a.name || ""))
      .filter((name) => name)
      .join(" and ");
  }

  function bibtexKey(paper) {
    const first = (paper.authors || [])
      .map((a) => (typeof a === "string" ? a : a.name || ""))
      .find((name) => name);
    const last = first ? first.trim().split(/\s+/).pop() : "unknown";
    const year = paper.year || "nodate";
    const word = (paper.title || "untitled").trim().split(/\s+/)[0] || "untitled";
    return `${last}${year}${word}`.replace(/[^A-Za-z0-9]/g, "");
  }

  function bibtexEntry(paper) {
    const fields = [
      `  title = {${bibtexEscape(paper.title || "Untitled")}}`,
      `  author = {${bibtexEscape(bibtexAuthors(paper))}}`,
    ];
    if (paper.year) fields.push(`  year = {${bibtexEscape(paper.year)}}`);
    if (paper.journal) fields.push(`  journal = {${bibtexEscape(paper.journal)}}`);
    if (paper.doi) fields.push(`  doi = {${bibtexEscape(paper.doi)}}`);
    if (paper.abstract) fields.push(`  abstract = {${bibtexEscape(paper.abstract)}}`);
    return `@article{${bibtexKey(paper)},\n${fields.join(",\n")}\n}`;
  }

  function selectedBibtex() {
    return selectedPapers().map(bibtexEntry).join("\n\n");
  }

  function openSelectedUrls() {
    const papers = selectedPapers();
    if (!papers.length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("Select results first.");
      return;
    }
    const urls = papers
      .filter((paper) => paper.doi)
      .map((paper) => `https://doi.org/${paper.doi}`);
    if (!urls.length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("No DOI links in selection.");
      return;
    }
    // Direct click handler: one window.open per URL keeps the popup
    // blocker satisfied the same way hub's toolbar button does.
    urls.forEach((url) => window.open(url, "_blank", "noopener"));
    if (bulkStatus) bulkStatus.textContent = "";
  }

  function downloadSelectedBibtex() {
    const papers = selectedPapers();
    if (!papers.length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("Select results first.");
      return;
    }
    const blob = new Blob([selectedBibtex()], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `scholar-selected-${new Date().toISOString().slice(0, 10)}.bib`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function renderResults(data) {
    const papers = data.results || [];
    lastPapers = papers;
    selected.clear();
    refreshSourceOptions();
    resultsContent.replaceChildren();

    const visible = viewPapers();
    if (!visible.length) {
      const empty = document.createElement("div");
      empty.className = "empty-message";
      empty.textContent = scholarT("No papers matched this query.");
      resultsContent.appendChild(empty);
    } else {
      visible.forEach(({ paper, index }) =>
        resultsContent.appendChild(renderPaper(paper, index)),
      );
    }
    syncSelectAll();

    const metadata = data.metadata || {};
    // Declutter (CCT4429): header meta is count + corpus tier only. The
    // cached flag and the search mode already have visible owners (the
    // request path and the Advanced block's source control); repeating them
    // here is the clutter the operator flagged.
    const parts = [`${papers.length} paper${papers.length === 1 ? "" : "s"}`];
    // READINESS: which corpus answered. The configured policy is local-first,
    // and the user (and a bug report) must be able to see when the network was
    // actually needed -- a silent fallback is indistinguishable from a local
    // hit that happened to work. An explicit Sources selection reports
    // itself plus the per-engine counts (old-direct's inline source status).
    if (metadata.source_tier === "selected") {
      parts.push(scholarT("Selected sources"));
    } else if (metadata.source_tier) {
      parts.push(
        metadata.source_tier === "primary"
          ? scholarT("Local corpus (NAS)")
          : scholarT("Online fallback"),
      );
    }
    const counts = metadata.engine_counts || {};
    const counted = Object.keys(counts);
    if (counted.length) {
      // Per-source options are corpus proper nouns and stay as-is (same
      // convention as the source filter's dynamically built options).
      parts.push(counted.map((name) => `${name} ${counts[name]}`).join(", "));
    }
    stats.textContent = parts.join(" · ");
    show(results);
  }

  function selectedPapers() {
    return lastPapers.filter((paper, index) =>
      selected.has(paperKey(paper, index)),
    );
  }

  function setBulkBusy(btn, busy) {
    [saveSelectedBtn, enrichSelectedBtn].forEach((b) => {
      if (b) b.disabled = busy;
    });
    if (btn && busy && !btn.dataset.label) {
      btn.dataset.label = btn.textContent;
      btn.textContent = scholarT("Saving…");
    } else if (btn && !busy && btn.dataset.label) {
      btn.textContent = btn.dataset.label;
      delete btn.dataset.label;
    }
  }

  async function saveSelected() {
    const papers = selectedPapers();
    if (!papers.length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("Select results to save.");
      return;
    }
    setBulkBusy(saveSelectedBtn, true);
    if (bulkStatus) bulkStatus.textContent = "";
    try {
      const resp = await fetch(`${STX_MOUNT}/api/library/save-bulk`, {
        method: "POST",
        headers: csrfHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ papers: papers.map(savePayload), project: currentProject() }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || scholarT("Save failed"));
      const saved = (data.saved || []).length;
      const failed = (data.failed || []).length;
      if (bulkStatus) {
        bulkStatus.textContent = scholarT("Saved %(saved)s of %(total)s", {
          saved,
          total: saved + failed,
        });
      }
    } catch (err) {
      showError(`${scholarT("Save failed")}: ${err.message}`, saveSelected);
    } finally {
      setBulkBusy(saveSelectedBtn, false);
    }
  }

  async function enrichSelected() {
    const papers = selectedPapers().slice(0, ENRICH_LIMIT);
    if (!selectedPapers().length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("Select results to save.");
      return;
    }
    setBulkBusy(enrichSelectedBtn, true);
    if (bulkStatus) bulkStatus.textContent = "";
    try {
      let enriched = 0;
      for (const paper of papers) {
        const libraryId = await saveOne(paper);
        const params = new URLSearchParams({ paper_id: libraryId });
        const resp = await fetch(`${STX_MOUNT}/api/library/enrich`, {
          method: "POST",
          headers: csrfHeaders({
            "Content-Type": "application/x-www-form-urlencoded",
          }),
          body: params.toString(),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || scholarT("Save failed"));
        enriched += 1;
      }
      if (bulkStatus) {
        bulkStatus.textContent = scholarT("Enriched %(done)s of %(total)s", {
          done: enriched,
          total: selectedPapers().length,
        });
      }
    } catch (err) {
      showError(`${scholarT("Save failed")}: ${err.message}`, enrichSelected);
    } finally {
      setBulkBusy(enrichSelectedBtn, false);
    }
  }

  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      resultsContent.replaceChildren();
      const visible = viewPapers();
      visible.forEach(({ paper, index }) =>
        resultsContent.appendChild(renderPaper(paper, index)),
      );
      syncSelectAll();
    });
  }
  if (sourceFilter) {
    sourceFilter.addEventListener("change", () => {
      resultsContent.replaceChildren();
      const visible = viewPapers();
      visible.forEach(({ paper, index }) =>
        resultsContent.appendChild(renderPaper(paper, index)),
      );
      syncSelectAll();
    });
  }
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      const visible = viewPapers().map(({ paper, index }) =>
        paperKey(paper, index),
      );
      if (selectAll.checked) visible.forEach((key) => selected.add(key));
      else visible.forEach((key) => selected.delete(key));
      resultsContent.replaceChildren();
      viewPapers().forEach(({ paper, index }) =>
        resultsContent.appendChild(renderPaper(paper, index)),
      );
    });
  }
  if (saveSelectedBtn) saveSelectedBtn.addEventListener("click", saveSelected);
  if (enrichSelectedBtn) {
    enrichSelectedBtn.addEventListener("click", enrichSelected);
  }
  // Slice 11: save-then-download. Search rows are not library papers, so
  // the pill files the selection first (existing save-bulk), then fetches
  // OA PDFs for the filed ids (max 10 per the endpoint cap).
  async function downloadSelectedPdfs() {
    const papers = selectedPapers();
    if (!papers.length) {
      if (bulkStatus) bulkStatus.textContent = scholarT("Select results to save.");
      return;
    }
    if (downloadPdfsBtn) downloadPdfsBtn.disabled = true;
    if (bulkStatus) bulkStatus.textContent = "";
    try {
      const saveResp = await fetch(`${STX_MOUNT}/api/library/save-bulk`, {
        method: "POST",
        headers: csrfHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ papers: papers.map(savePayload), project: currentProject() }),
      });
      const saved = await saveResp.json();
      if (!saveResp.ok) throw new Error(saved.error || scholarT("Save failed"));
      const ids = (saved.saved || []).map((row) => row.library_id).filter((id) => id);
      if (!ids.length) throw new Error(scholarT("Save failed"));
      const dlResp = await fetch(`${STX_MOUNT}/api/library/download-pdfs`, {
        method: "POST",
        headers: csrfHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ library_ids: ids.slice(0, 10) }),
      });
      const data = await dlResp.json();
      if (!dlResp.ok) throw new Error(data.error || scholarT("Download failed"));
      const done = (data.downloaded || []).length;
      const failed = (data.failed || []).length;
      if (bulkStatus) {
        bulkStatus.textContent = scholarT("Downloaded %(done)s of %(total)s PDFs", {
          done,
          total: done + failed,
        });
      }
    } catch (err) {
      showError(`${scholarT("Download failed")}: ${err.message}`, downloadSelectedPdfs);
    } finally {
      if (downloadPdfsBtn) downloadPdfsBtn.disabled = false;
    }
  }
  if (downloadPdfsBtn) {
    downloadPdfsBtn.addEventListener("click", downloadSelectedPdfs);
  }
  // Slice 3: header tools over the checked rows (hub results-header parity).
  if (abstractToggle) {
    abstractToggle.addEventListener("click", () => {
      abstractFull = !abstractFull;
      applyAbstractMode();
    });
  }
  if (openUrlsBtn) openUrlsBtn.addEventListener("click", openSelectedUrls);
  if (exportBibtexBtn) {
    exportBibtexBtn.addEventListener("click", downloadSelectedBibtex);
  }
  document.addEventListener("keydown", (event) => {
    // Hub parity: Ctrl/Cmd+C copies selected BibTeX when no text is
    // selected. Unlike hub, keystrokes inside inputs are never hijacked --
    // copying from the query box must keep working.
    const target = event.target;
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.shiftKey &&
      !event.altKey &&
      (event.key === "c" || event.key === "C")
    ) {
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      const selection = window.getSelection();
      if (selection && selection.toString().trim().length > 0) return;
      const papers = selectedPapers();
      if (!papers.length) return;
      event.preventDefault();
      navigator.clipboard
        .writeText(selectedBibtex())
        .then(() => {
          if (bulkStatus) {
            bulkStatus.textContent =
              papers.length === 1
                ? scholarT("Copied %(n)s BibTeX entry", { n: papers.length })
                : scholarT("Copied %(n)s BibTeX entries", { n: papers.length });
          }
        })
        .catch(() => {
          if (bulkStatus) bulkStatus.textContent = scholarT("Copy failed");
        });
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) {
      showError("Enter a search query.");
      return;
    }

    hide(errorBox);
    hide(results);
    show(loading);

    try {
      const params = new URLSearchParams({
        q: query,
        max_results: maxResults.value,
      });
      if (modeSelect) params.set("mode", modeSelect.value);
      if (sourcesGrid) {
        // Old-direct Sources semantics: the checked set travels as
        // ?sources=a,b,c. All (or none) checked is the tiered default --
        // omit the param so the request behaves exactly as before.
        const boxes = Array.from(
          sourcesGrid.querySelectorAll("input.source-toggle"),
        );
        const checked = boxes
          .filter((box) => box.checked)
          .map((box) => box.value);
        if (checked.length && checked.length < boxes.length) {
          params.set("sources", checked.join(","));
        }
      }
      // Slice 2: range filters travel only when set; the backend fails
      // closed (400) on malformed values and surfaces the message.
      Object.keys(filterInputs).forEach((name) => {
        const el = filterInputs[name];
        if (el && el.value.trim() !== "") params.set(name, el.value.trim());
      });
      if (noCache && noCache.checked) params.set("no_cache", "true");
      const response = await fetch(`${STX_MOUNT}/api/search?${params}`);
      const data = await response.json();

      if (!response.ok) {
        showError(
          data.error || `Search failed (${response.status})`,
          () => form.requestSubmit(),
        );
        return;
      }
      renderResults(data);
    } catch (err) {
      showError(`Search failed: ${err.message}`, () => form.requestSubmit());
    } finally {
      hide(loading);
    }
  });
});
