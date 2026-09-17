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
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("searchForm");
  if (!form) return;

  const input = document.getElementById("searchInput");
  const maxResults = document.getElementById("searchMaxResults");
  const modeSelect = document.getElementById("searchMode");
  const noCache = document.getElementById("searchNoCache");
  const loading = document.getElementById("searchLoading");
  const errorBox = document.getElementById("searchError");
  const errorMessage = document.getElementById("searchErrorMessage");
  const results = document.getElementById("searchResults");
  const resultsContent = document.getElementById("searchResultsContent");
  const stats = document.getElementById("searchStats");

  const show = (el) => el && el.classList.remove("hidden");
  const hide = (el) => el && el.classList.add("hidden");

  function showError(message) {
    errorMessage.textContent = message;
    show(errorBox);
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
    const graphTab = document.querySelector('.tab-btn[data-tab="graph"]');
    if (graphTab) graphTab.click();
    if (doiInput) doiInput.focus();
  }

  function renderPaper(paper) {
    const item = document.createElement("div");
    item.className = "search-result";

    const title = document.createElement("div");
    title.className = "search-result__title";
    // textContent, not innerHTML: titles and abstracts are third-party data.
    title.textContent = paper.title || scholarT("Untitled");
    item.appendChild(title);

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
    item.appendChild(meta);

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

      item.appendChild(doiLine);
    }

    if (paper.abstract) {
      const abstract = document.createElement("div");
      abstract.className = "search-result__abstract";
      const text = paper.abstract;
      abstract.textContent =
        text.length > 300 ? `${text.slice(0, 300)}...` : text;
      item.appendChild(abstract);
    }

    return item;
  }

  function renderResults(data) {
    const papers = data.results || [];
    resultsContent.replaceChildren();

    if (!papers.length) {
      const empty = document.createElement("div");
      empty.className = "empty-message";
      empty.textContent = scholarT("No papers matched this query.");
      resultsContent.appendChild(empty);
    } else {
      papers.forEach((paper) => resultsContent.appendChild(renderPaper(paper)));
    }

    const metadata = data.metadata || {};
    const parts = [`${papers.length} paper${papers.length === 1 ? "" : "s"}`];
    if (metadata.cached) parts.push("cached");
    if (metadata.search_mode) parts.push(metadata.search_mode);
    // READINESS: which corpus answered. The configured policy is local-first,
    // and the user (and a bug report) must be able to see when the network was
    // actually needed -- a silent fallback is indistinguishable from a local
    // hit that happened to work.
    if (metadata.source_tier) {
      parts.push(
        metadata.source_tier === "primary"
          ? scholarT("Local corpus (NAS)")
          : scholarT("Online fallback"),
      );
    }
    stats.textContent = parts.join(" · ");
    show(results);
  }

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
      if (noCache && noCache.checked) params.set("no_cache", "true");
      const response = await fetch(`${STX_MOUNT}/api/search?${params}`);
      const data = await response.json();

      if (!response.ok) {
        showError(data.error || `Search failed (${response.status})`);
        return;
      }
      renderResults(data);
    } catch (err) {
      showError(`Search failed: ${err.message}`);
    } finally {
      hide(loading);
    }
  });
});
