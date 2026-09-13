/**
 * Scholar GUI - Library tab
 *
 * Lists the user's local library (GET /api/library) and offers a contextual
 * per-paper Enrich action (POST /api/library/enrich). Enrichment is an
 * operation ON a library item, not a top-level tab (#106); the tab bar is
 * unchanged. All data and enrichment logic lives in the package behind these
 * two endpoints -- this file only renders and wires the action.
 *
 * The list is loaded lazily when the Library tab is first activated, so the
 * default tab (Search) does not pay for it.
 */
document.addEventListener("DOMContentLoaded", () => {
  const listPanel = document.getElementById("tab-library");
  if (!listPanel) return;

  const listEl = document.getElementById("libraryList");
  const loadingEl = document.getElementById("libraryLoading");
  const errorEl = document.getElementById("libraryError");
  const errorMsgEl = document.getElementById("libraryErrorMessage");
  const statsEl = document.getElementById("libraryStats");

  const show = (el) => el && el.classList.remove("hidden");
  const hide = (el) => el && el.classList.add("hidden");
  let loaded = false;

  function formatAuthors(paper) {
    const authors = paper.authors || [];
    if (!authors.length) return "";
    const names = authors.map((a) => (typeof a === "string" ? a : a.name || ""));
    return names.length > 3
      ? `${names.slice(0, 3).join(", ")} et al.`
      : names.join(", ");
  }

  function makeRow(paper) {
    const item = document.createElement("div");
    item.className = "library-item";
    item.dataset.paperId = paper.paper_id || "";

    const main = document.createElement("div");
    main.className = "library-item__main";

    const title = document.createElement("div");
    title.className = "library-item__title";
    title.textContent = paper.title || paper.paper_id || "Untitled";
    main.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "library-item__meta";
    const bits = [formatAuthors(paper), paper.year && String(paper.year), paper.venue].filter(
      (b) => b,
    );
    bits.forEach((text) => {
      const span = document.createElement("span");
      span.textContent = text;
      meta.appendChild(span);
    });
    if (bits.length) main.appendChild(meta);

    if (paper.doi) {
      const doi = document.createElement("div");
      doi.className = "library-item__meta";
      const link = document.createElement("a");
      link.href = `https://doi.org/${paper.doi}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = paper.doi;
      doi.appendChild(link);
      main.appendChild(doi);
    }

    // Enrichment status line (filled in after an enrich round-trip).
    const status = document.createElement("div");
    status.className = "library-item__enrich-status";
    if (paper.abstract || paper.citation_count) {
      const parts = [];
      if (paper.abstract) parts.push("abstract");
      if (paper.citation_count) parts.push(`${paper.citation_count} citations`);
      status.textContent = `Enriched: ${parts.join(", ")}`;
    }
    main.appendChild(status);

    const actions = document.createElement("div");
    actions.className = "library-item__actions";
    const enrichBtn = document.createElement("button");
    enrichBtn.type = "button";
    enrichBtn.className = "library-enrich-btn";
    enrichBtn.textContent = "Enrich";
    enrichBtn.addEventListener("click", () =>
      enrich(paper, enrichBtn, status),
    );
    actions.appendChild(enrichBtn);

    item.appendChild(main);
    item.appendChild(actions);
    return item;
  }

  async function enrich(paper, btn, statusEl) {
    btn.disabled = true;
    btn.textContent = "Enriching\u2026";
    statusEl.textContent = "";
    try {
      const params = new URLSearchParams({ paper_id: paper.paper_id });
      const resp = await fetch(`${STX_MOUNT}/api/library/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `Enrichment failed (${resp.status})`);
      // Reflect the fresh metadata on the row without a full reload.
      if (data.abstract_chars) {
        statusEl.textContent = `Enriched: ${data.abstract_chars}-char abstract` +
          (data.citation_count ? `, ${data.citation_count} citations` : "");
      }
      if (data.title) {
        const t = btn.closest(".library-item").querySelector(".library-item__title");
        if (t) t.textContent = data.title;
      }
    } catch (err) {
      statusEl.textContent = `Enrichment failed: ${err.message}`;
      statusEl.classList.add("library-item__enrich-status--error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Enrich";
    }
  }

  async function loadLibrary(force = false) {
    if (loaded && !force) return;
    hide(errorEl);
    show(loadingEl);
    try {
      const resp = await fetch(`${STX_MOUNT}/api/library`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `Library load failed (${resp.status})`);
      hide(loadingEl);
      listEl.replaceChildren();
      const papers = data.papers || [];
      if (statsEl) statsEl.textContent = `${papers.length} paper${papers.length === 1 ? "" : "s"}`;
      if (!papers.length) {
        const empty = document.createElement("div");
        empty.className = "empty-message";
        empty.textContent =
          "Your library is empty. Save papers from Search or Import, then Enrich them here.";
        listEl.appendChild(empty);
      } else {
        papers.forEach((p) => listEl.appendChild(makeRow(p)));
      }
      loaded = true;
    } catch (err) {
      hide(loadingEl);
      errorMsgEl.textContent = String(err.message || err);
      show(errorEl);
    }
  }

  // --- Import / Export (#106 / L327) ----------------------------------------
  const ioStatus = document.getElementById("libraryIoStatus");
  function setIoStatus(msg, isErr) {
    if (!ioStatus) return;
    ioStatus.textContent = msg;
    ioStatus.classList.toggle("library-io__status--error", !!isErr);
  }

  const exportBtn = document.getElementById("libraryExportBtn");
  if (exportBtn) {
    exportBtn.addEventListener("click", async () => {
      const fmt = (document.getElementById("libraryExportFormat") || {}).value || "bibtex";
      exportBtn.disabled = true;
      setIoStatus(`Exporting as ${fmt}…`);
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/export?format=${encodeURIComponent(fmt)}`);
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.error || `Export failed (${resp.status})`);
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const ext = { bibtex: "bib", ris: "ris", endnote: "enw" }[fmt] || "txt";
        a.href = url;
        a.download = `scholar-library.${ext}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setIoStatus(`Exported library as ${fmt}.`);
      } catch (err) {
        setIoStatus(String(err.message || err), true);
      } finally {
        exportBtn.disabled = false;
      }
    });
  }

  const importBtn = document.getElementById("libraryImportBtn");
  const importFile = document.getElementById("libraryImportFile");
  if (importBtn && importFile) {
    importBtn.addEventListener("click", () => importFile.click());
    importFile.addEventListener("change", async () => {
      const file = importFile.files && importFile.files[0];
      if (!file) return;
      importBtn.disabled = true;
      setIoStatus(`Importing ${file.name}…`);
      try {
        const text = await file.text();
        const params = new URLSearchParams({ format: "bibtex", bibtex: text });
        // CSRF: the mounted hub enables CsrfViewMiddleware, so the Import POST
        // must carry the token. Read it from the hidden input rendered by the
        // {% csrf_token %} tag (populated by the middleware when enabled;
        // empty/inert standalone).
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        const csrf = csrfInput ? csrfInput.value : "";
        const headers = { "Content-Type": "application/x-www-form-urlencoded" };
        if (csrf) headers["X-CSRFToken"] = csrf;
        const resp = await fetch(`${STX_MOUNT}/api/library/import`, {
          method: "POST",
          headers,
          body: params.toString(),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Import failed (${resp.status})`);
        setIoStatus(`Imported ${data.imported} paper${data.imported === 1 ? "" : "s"} from ${file.name}.`);
        importFile.value = "";
        loadLibrary(true); // refresh the list to show the imported papers
      } catch (err) {
        setIoStatus(String(err.message || err), true);
      } finally {
        importBtn.disabled = false;
      }
    });
  }

  // Lazy-load the list the first time the Library tab is activated.
  const libTabBtn = document.querySelector('.tab-btn[data-tab="library"]');
  if (libTabBtn) {
    libTabBtn.addEventListener("click", () => {
      if (!loaded) loadLibrary();
    });
  }
  // If the page loads with Library already active (it does not by default), load now.
  if (listPanel.classList.contains("active")) loadLibrary();
});
