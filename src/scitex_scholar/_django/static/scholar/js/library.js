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
  const filterEl = document.getElementById("libraryFilter");
  const filterClearEl = document.getElementById("libraryFilterClear");

  const show = (el) => el && el.classList.remove("hidden");
  const hide = (el) => el && el.classList.add("hidden");
  let loaded = false;
  let filterTimer = null;

  // Project sync (parity slice 3c): the header picker navigates with
  // ?project=<id> (the SDK picker's default contract), so the selection is
  // readable here with no extra state. Saves elsewhere (search.js) file
  // into the same selection; the list filters to it server-side.
  function currentProject() {
    try {
      return new URLSearchParams(window.location.search).get("project") || "";
    } catch (e) {
      return "";
    }
  }

  // Project chips + sync indicator, from the existing /api/projects
  // endpoint (the picker's provider contract). Chips navigate with
  // ?project= so the server resolves and remembers the selection.
  const projectChipsEl = document.getElementById("libraryProjectChips");
  const projectCurrentEl = document.getElementById("libraryProjectCurrent");
  async function loadProjectChips() {
    if (!projectChipsEl && !projectCurrentEl) return;
    const current = currentProject();
    if (projectCurrentEl) {
      projectCurrentEl.textContent = current
        ? scholarT("Project: %(project)s", { project: current })
        : scholarT("All projects");
    }
    if (!projectChipsEl || projectChipsEl.dataset.done) return;
    try {
      const resp = await fetch(`${STX_MOUNT}/api/projects`);
      const data = await resp.json();
      if (!resp.ok) return;
      projectChipsEl.dataset.done = "1";
      const all = document.createElement("a");
      all.className = "library-project__chip" + (current ? "" : " library-project__chip--active");
      all.href = window.location.pathname;
      all.textContent = scholarT("All projects");
      projectChipsEl.appendChild(all);
      (data.projects || []).forEach((p) => {
        const chip = document.createElement("a");
        const id = typeof p === "string" ? p : p.id || "";
        if (!id) return;
        chip.className = "library-project__chip" + (id === current ? " library-project__chip--active" : "");
        chip.href = `${window.location.pathname}?project=${encodeURIComponent(id)}`;
        chip.textContent = (typeof p === "string" ? p : p.name || p.id) || "";
        projectChipsEl.appendChild(chip);
      });
    } catch (e) {
      /* chips are progressive enhancement; the list still loads */
    }
  }

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

    // Project sync (parity slice 3c): filed papers show their projects.
    if (paper.projects && paper.projects.length) {
      const proj = document.createElement("div");
      proj.className = "library-item__projects";
      paper.projects.forEach((name) => {
        const chip = document.createElement("span");
        chip.className = "library-project__chip library-project__chip--static";
        chip.textContent = name;
        proj.appendChild(chip);
      });
      main.appendChild(proj);
    }

    // Enrichment status line (filled in after an enrich round-trip).
    const status = document.createElement("div");
    status.className = "library-item__enrich-status";
    if (paper.abstract || paper.citation_count) {
      const parts = [];
      if (paper.abstract) parts.push("abstract");
      if (paper.citation_count) parts.push(`${paper.citation_count} citations`);
      status.textContent = scholarT("Enriched: %(parts)s", { parts: parts.join(", ") });
    }
    main.appendChild(status);

    const actions = document.createElement("div");
    actions.className = "library-item__actions";
    const enrichBtn = document.createElement("button");
    enrichBtn.type = "button";
    enrichBtn.className = "library-enrich-btn";
    enrichBtn.textContent = scholarT("Enrich");
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
    btn.textContent = scholarT("Enriching…");
    statusEl.textContent = "";
    try {
      const params = new URLSearchParams({ paper_id: paper.paper_id });
      const resp = await fetch(`${STX_MOUNT}/api/library/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || scholarT("Enrichment failed (HTTP %(status)s)", { status: resp.status }));
      // Reflect the fresh metadata on the row without a full reload.
      if (data.abstract_chars) {
        const parts = [
          data.abstract_chars + " " + scholarT("char abstract"),
        ];
        if (data.citation_count) {
          parts.push(data.citation_count + " " + scholarT("citations"));
        }
        statusEl.textContent = scholarT("Enriched: %(parts)s", { parts: parts.join(", ") });
      }
      if (data.title) {
        const t = btn.closest(".library-item").querySelector(".library-item__title");
        if (t) t.textContent = data.title;
      }
    } catch (err) {
      statusEl.textContent = scholarT("Enrichment failed") + ": " + err.message;
      statusEl.classList.add("library-item__enrich-status--error");
    } finally {
      btn.disabled = false;
      btn.textContent = scholarT("Enrich");
    }
  }

  /**
   * The two empty states, each with the actions that ACTUALLY exist.
   *
   * Review blocker 2: the old copy told the user to "save a paper from
   * Search", but Search exposes no save action or endpoint -- so the state
   * named an action the user could not take. What exists is Import (the
   * button above, wired to /api/library/import) and, when a filter matched
   * nothing, clearing that filter. Both actions are rendered here as real
   * controls rather than described in prose, and the filtered variant is only
   * reachable because the filter box now exists.
   */
  function emptyState(data) {
    const empty = document.createElement("div");
    empty.className = "empty-message";

    if (data.filtered) {
      const text = document.createElement("div");
      text.textContent = scholarT("No papers match the current filters.");
      empty.appendChild(text);
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "btn-control-library";
      clear.textContent = scholarT("Clear filters");
      clear.addEventListener("click", () => {
        if (filterEl) filterEl.value = "";
        loadLibrary(true);
      });
      empty.appendChild(clear);
      return empty;
    }

    const text = document.createElement("div");
    text.textContent = scholarT("Your library is empty. Import a BibTeX file to add papers.");
    empty.appendChild(text);
    const importBtn = document.getElementById("libraryImportBtn");
    if (importBtn) {
      const go = document.createElement("button");
      go.type = "button";
      go.className = "btn-control-library";
      go.textContent = scholarT("Import BibTeX");
      go.addEventListener("click", () => importBtn.click());
      empty.appendChild(go);
    }
    return empty;
  }

  async function loadLibrary(force = false) {
    if (loaded && !force) return;
    hide(errorEl);
    show(loadingEl);
    const query = filterEl ? filterEl.value.trim() : "";
    if (filterClearEl) filterClearEl.classList.toggle("hidden", !query);
    try {
      // Project sync: the list follows the header picker's ?project=
      // selection server-side (same endpoint, no new backend). The filter
      // shape stays `/api/library?q=` first so the flag contract holds.
      const qp = [];
      if (query) qp.push(`q=${encodeURIComponent(query)}`);
      const project = currentProject();
      if (project) qp.push(`project=${encodeURIComponent(project)}`);
      const url = qp.length
        ? `${STX_MOUNT}/api/library?${qp.join("&")}`
        : `${STX_MOUNT}/api/library`;
      const resp = await fetch(url);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `Library load failed (${resp.status})`);
      hide(loadingEl);
      listEl.replaceChildren();
      const papers = data.papers || [];
      if (statsEl) {
        const n = papers.length;
        statsEl.textContent = data.filtered
          ? scholarT("%(count)s of %(total)s Papers", { count: n, total: data.total })
          : n + " " + scholarT(n === 1 ? "Paper" : "Papers");
      }
      if (!papers.length) {
        listEl.appendChild(emptyState(data));
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
        // A dict keyed call, not a template literal: scholarT looks the string
        // up verbatim, so an interpolated literal could never match the
        // catalog and the JA page showed English here (review blocker 2).
        setIoStatus(
          scholarT(
            data.imported === 1
              ? "Imported %(n)s paper from %(file)s"
              : "Imported %(n)s papers from %(file)s",
            { n: data.imported, file: file.name },
          ),
        );
        importFile.value = "";
        loadLibrary(true); // refresh the list to show the imported papers
      } catch (err) {
        setIoStatus(String(err.message || err), true);
      } finally {
        importBtn.disabled = false;
      }
    });
  }

  // --- External imports: Zotero + Connected Papers (parity slice 3b) ----
  // Thin reflection over thin views (same class as the BibTeX IO above):
  // status lines probe availability on first Library activation; imports
  // POST JSON with the CSRF header the mounted hub requires. "Download
  // BibTeX for Zotero" reuses the existing BibTeX export flow (hub's
  // Zotero export IS a BibTeX download), so no new endpoint, no new
  // strings.
  function csrfJsonHeaders() {
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const headers = { "Content-Type": "application/json" };
    if (csrfInput && csrfInput.value) headers["X-CSRFToken"] = csrfInput.value;
    return headers;
  }

  function setExtStatus(id, msg, isErr) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("library-io__status--error", !!isErr);
  }

  let extChecked = false;
  async function checkExtStatuses() {
    if (extChecked) return;
    extChecked = true;
    const zoteroStatus = document.getElementById("zoteroStatus");
    const cpStatus = document.getElementById("cpStatus");
    try {
      const zr = await fetch(`${STX_MOUNT}/api/library/zotero/status`);
      const zd = await zr.json();
      if (zoteroStatus) {
        zoteroStatus.textContent = zd.available
          ? scholarT("Zotero database found")
          : scholarT("Zotero database not found");
      }
      if (zd.available) {
        const cr = await fetch(`${STX_MOUNT}/api/library/zotero/collections`);
        if (cr.ok) {
          const cd = await cr.json();
          const sel = document.getElementById("zoteroCollection");
          if (sel && Array.isArray(cd.collections)) {
            sel.replaceChildren();
            cd.collections.forEach((name) => {
              const opt = document.createElement("option");
              opt.value = name;
              opt.textContent = name;
              sel.appendChild(opt);
            });
          }
        }
      } else {
        ["zoteroMode", "zoteroImportBtn"].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.disabled = true;
        });
      }
    } catch (err) {
      if (zoteroStatus) zoteroStatus.textContent = scholarT("Zotero database not found");
    }
    try {
      const cr = await fetch(`${STX_MOUNT}/api/library/connected-papers/status`);
      const cd = await cr.json();
      if (cpStatus) {
        cpStatus.textContent = cd.available
          ? scholarT("Connected Papers available")
          : scholarT("Connected Papers unavailable");
      }
      if (!cd.available) {
        const btn = document.getElementById("cpImportBtn");
        if (btn) btn.disabled = true;
      }
    } catch (err) {
      if (cpStatus) cpStatus.textContent = scholarT("Connected Papers unavailable");
    }
  }

  const zoteroMode = document.getElementById("zoteroMode");
  const zoteroCollection = document.getElementById("zoteroCollection");
  const zoteroTags = document.getElementById("zoteroTags");
  if (zoteroMode) {
    zoteroMode.addEventListener("change", () => {
      if (zoteroCollection) zoteroCollection.hidden = zoteroMode.value !== "collection";
      if (zoteroTags) zoteroTags.hidden = zoteroMode.value !== "tags";
    });
  }

  const zoteroImportBtn = document.getElementById("zoteroImportBtn");
  if (zoteroImportBtn) {
    zoteroImportBtn.addEventListener("click", async () => {
      const mode = (zoteroMode && zoteroMode.value) || "all";
      const body = { mode };
      if (mode === "collection" && zoteroCollection) body.collection = zoteroCollection.value;
      if (mode === "tags" && zoteroTags) body.tags = zoteroTags.value;
      zoteroImportBtn.disabled = true;
      setExtStatus("zoteroIoStatus", scholarT("Importing…"));
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/zotero/import`, {
          method: "POST",
          headers: csrfJsonHeaders(),
          body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || scholarT("Import failed"));
        setExtStatus(
          "zoteroIoStatus",
          scholarT("Imported %(imported)s of %(total)s papers", {
            imported: data.imported,
            total: data.total,
          }),
        );
        loadLibrary(true);
      } catch (err) {
        setExtStatus("zoteroIoStatus", `${scholarT("Import failed")}: ${err.message}`, true);
      } finally {
        zoteroImportBtn.disabled = false;
      }
    });
  }

  const zoteroExportBtn = document.getElementById("zoteroExportBtn");
  if (zoteroExportBtn && exportBtn) {
    zoteroExportBtn.addEventListener("click", () => {
      const fmt = document.getElementById("libraryExportFormat");
      if (fmt) fmt.value = "bibtex";
      exportBtn.click();
    });
  }

  const cpImportBtn = document.getElementById("cpImportBtn");
  const cpPaperId = document.getElementById("cpPaperId");
  if (cpImportBtn) {
    cpImportBtn.addEventListener("click", async () => {
      const paperId = (cpPaperId && cpPaperId.value.trim()) || "";
      if (!paperId) {
        setExtStatus("cpIoStatus", scholarT("Enter a Semantic Scholar paper ID"), true);
        return;
      }
      cpImportBtn.disabled = true;
      setExtStatus("cpIoStatus", scholarT("Importing…"));
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/connected-papers/import`, {
          method: "POST",
          headers: csrfJsonHeaders(),
          body: JSON.stringify({ paper_id: paperId }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error || scholarT("Import failed"));
        setExtStatus(
          "cpIoStatus",
          scholarT("Imported %(imported)s of %(total)s papers", {
            imported: data.imported,
            total: data.total,
          }),
        );
        loadLibrary(true);
      } catch (err) {
        setExtStatus("cpIoStatus", `${scholarT("Import failed")}: ${err.message}`, true);
      } finally {
        cpImportBtn.disabled = false;
      }
    });
  }

  // Lazy-load the list the first time the Library tab is activated.
  const libTabBtn = document.querySelector('.tab-btn[data-tab="library"]');
  if (libTabBtn) {
    libTabBtn.addEventListener("click", () => {
      if (!loaded) loadLibrary();
      loadProjectChips();
      checkExtStatuses();
    });
  }
  // Filter: debounced server-side query (?q=). Typing before the list has ever
  // loaded also triggers the first load, so the filtered empty state is
  // reachable on a fresh page.
  if (filterEl) {
    filterEl.addEventListener("input", () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => loadLibrary(true), 250);
    });
  }
  if (filterClearEl) {
    filterClearEl.addEventListener("click", () => {
      if (filterEl) filterEl.value = "";
      loadLibrary(true);
    });
  }
  // If the page loads with Library already active (it does not by default), load now.
  if (listPanel.classList.contains("active")) {
    loadLibrary();
    loadProjectChips();
    checkExtStatuses();
  }
});
