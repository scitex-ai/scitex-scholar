/**
 * Scholar GUI - Search tab
 *
 * Submits the query to /api/search and renders the results. All search
 * logic (query parsing, engine selection, ranking) belongs to the package's
 * ScholarSearchEngine behind that endpoint -- this file only renders.
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("searchForm");
  if (!form) return;

  const input = document.getElementById("searchInput");
  const maxResults = document.getElementById("searchMaxResults");
  const loading = document.getElementById("searchLoading");
  const errorBox = document.getElementById("searchError");
  const errorMessage = document.getElementById("searchErrorMessage");
  const results = document.getElementById("searchResults");
  const resultsContent = document.getElementById("searchResultsContent");
  const stats = document.getElementById("searchStats");

  const show = (el) => el.classList.remove("hidden");
  const hide = (el) => el.classList.add("hidden");

  function showError(message) {
    errorMessage.textContent = message;
    show(errorBox);
  }

  function formatAuthors(paper) {
    const authors = paper.authors || [];
    if (!authors.length) return "Unknown authors";
    const names = authors.map((a) =>
      typeof a === "string" ? a : a.name || "",
    );
    return names.length > 3
      ? `${names.slice(0, 3).join(", ")} et al.`
      : names.join(", ");
  }

  function renderPaper(paper) {
    const item = document.createElement("div");
    item.className = "search-result";

    const title = document.createElement("div");
    title.className = "search-result__title";
    // textContent, not innerHTML: titles and abstracts are third-party data.
    title.textContent = paper.title || "Untitled";
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

    if (paper.doi) {
      const link = document.createElement("a");
      link.href = `https://doi.org/${paper.doi}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = paper.doi;
      const doiLine = document.createElement("div");
      doiLine.className = "search-result__meta";
      doiLine.appendChild(link);
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
      empty.textContent = "No papers matched this query.";
      resultsContent.appendChild(empty);
    } else {
      papers.forEach((paper) => resultsContent.appendChild(renderPaper(paper)));
    }

    const metadata = data.metadata || {};
    const parts = [`${papers.length} paper${papers.length === 1 ? "" : "s"}`];
    if (metadata.cached) parts.push("cached");
    if (metadata.search_mode) parts.push(metadata.search_mode);
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
      const response = await fetch(`api/search?${params}`);
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
