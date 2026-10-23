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
  const retryBtn = document.getElementById("libraryRetryBtn");
  if (retryBtn) {
    // Error fallback (UX standard): the load-failure state retries the same
    // force-reload the filter box already uses -- the list, not a blank.
    retryBtn.addEventListener("click", () => loadLibrary(true));
  }

  const show = (el) => el && el.classList.remove("hidden");
  const hide = (el) => el && el.classList.add("hidden");
  // Non-JSON guard (apps-lead probe 2026-10-22: an expired/missing
  // credential is 302'd to the hub login page, so the pane gets HTML
  // where JSON was expected). The login-page shape becomes a re-login
  // prompt; any other non-JSON body keeps its status. Every parse site
  // below goes through here so a wrong-content response never surfaces
  // a raw SyntaxError.
  async function readJson(resp) {
    const text = await resp.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch (err) {
      data = null;
    }
    if (data !== null) return data;
    const location = resp.url || "";
    const contentType = (resp.headers && resp.headers.get("content-type")) || "";
    const loginShaped =
      /login/i.test(location) &&
      (/text\/html/i.test(contentType) || /^\s*</.test(text));
    if (loginShaped) {
      throw new Error(scholarT("Session expired. Please log in again."));
    }
    throw new Error(
      scholarT("Server returned non-JSON (status %(status)s)", {
        status: resp.status,
      }),
    );
  }
  let loaded = false;
  let filterTimer = null;
  // Slice 4b (old-direct unification): the loaded rows stay cached so the
  // sort select re-renders client-side (hub sorts the list from its toolbar).
  let lastRows = [];
  const sortEl = document.getElementById("librarySort");

  function annotationOf(paper) {
    return (paper && paper.annotations) || {};
  }

  function importanceOf(paper) {
    const value = annotationOf(paper).importance;
    return typeof value === "number" ? value : 0;
  }

  function sortedRows() {
    const mode = sortEl ? sortEl.value : "relevance";
    const rows = lastRows.slice();
    const byTitle = (a, b) =>
      String(a.title || a.paper_id || "").localeCompare(
        String(b.title || b.paper_id || ""),
      );
    const byYear = (a, b) => (a.year || 0) - (b.year || 0);
    const byImportance = (a, b) => importanceOf(a) - importanceOf(b);
    if (mode === "title-asc") rows.sort(byTitle);
    else if (mode === "title-desc") rows.sort((a, b) => byTitle(b, a));
    else if (mode === "year-desc") rows.sort((a, b) => byYear(b, a));
    else if (mode === "year-asc") rows.sort(byYear);
    else if (mode === "importance-desc")
      rows.sort((a, b) => byImportance(b, a));
    else if (mode === "importance-asc") rows.sort(byImportance);
    return rows;
  }

  function renderRows() {
    if (!listEl) return;
    listEl.replaceChildren();
    sortedRows().forEach((p) => listEl.appendChild(makeRow(p)));
  }

  if (sortEl) {
    sortEl.addEventListener("change", () => {
      if (loaded) renderRows();
    });
  }

  // Project sync: the header picker's ?project=<id> (SDK picker default
  // contract) is readable here with no extra state. Saves elsewhere
  // (search.js) file into the same selection; the list filters to it
  // server-side. Operator 2026-10-23: NO project selector lives in the
  // Details strip — header picker only — so the chips + indicator that
  // used to mirror the selection here are deleted.
  function currentProject() {
    try {
      return new URLSearchParams(window.location.search).get("project") || "";
    } catch (e) {
      return "";
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

    // Slice 4b: annotation badges (reading status, stars, tags) render from
    // the row's annotations merge -- no extra round-trip.
    const badges = document.createElement("div");
    badges.className = "library-item__annotations";
    renderBadges(badges, paper);
    main.appendChild(badges);

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

    // Slice 4b: per-row Details toggle -- hub expands a details panel from
    // each library row (status, stars, tags, notes, save).
    const detailsToggle = document.createElement("button");
    detailsToggle.type = "button";
    detailsToggle.className = "library-details-toggle library-enrich-btn";
    detailsToggle.textContent = scholarT("Details");
    actions.appendChild(detailsToggle);

    item.appendChild(main);
    item.appendChild(actions);

    const details = makeDetails(paper, badges);
    details.hidden = true;
    detailsToggle.addEventListener("click", () => {
      details.hidden = !details.hidden;
    });
    item.appendChild(details);
    return item;
  }

  // Slice 4b: status radios + star rating + tags + notes, saved through the
  // slice-4a /api/library/annotate endpoint (partial merge, same doc the
  // list rows already carry).
  const READING_STATUSES = [
    ["to_read", "To read"],
    ["reading", "Reading"],
    ["read", "Read"],
    ["referenced", "Referenced"],
    ["favorite", "Favorite"],
  ];

  function renderBadges(badgesEl, paper) {
    badgesEl.replaceChildren();
    const ann = annotationOf(paper);
    if (ann.reading_status) {
      const chip = document.createElement("span");
      chip.className = "library-annotation__chip";
      const label = (READING_STATUSES.find(([v]) => v === ann.reading_status) || [])[1];
      chip.textContent = scholarT(label || ann.reading_status);
      badgesEl.appendChild(chip);
    }
    if (typeof ann.importance === "number" && ann.importance > 0) {
      const stars = document.createElement("span");
      stars.className = "library-annotation__stars";
      stars.textContent = "★".repeat(ann.importance) + "☆".repeat(5 - ann.importance);
      stars.title = scholarT("Importance");
      badgesEl.appendChild(stars);
    }
    (ann.tags || []).forEach((tag) => {
      const chip = document.createElement("span");
      chip.className = "library-annotation__chip library-annotation__chip--tag";
      chip.textContent = tag;
      badgesEl.appendChild(chip);
    });
  }

  function makeDetails(paper, badgesEl) {
    const ann = annotationOf(paper);
    const panel = document.createElement("div");
    panel.className = "library-item__details";

    const statusLabel = document.createElement("div");
    statusLabel.className = "library-details__label";
    statusLabel.textContent = scholarT("Reading status");
    panel.appendChild(statusLabel);

    const statusGroup = document.createElement("div");
    statusGroup.className = "library-details__status-group";
    const groupName = `reading-status-${paper.paper_id || Math.random().toString(36).slice(2)}`;
    READING_STATUSES.forEach(([value, label]) => {
      const option = document.createElement("label");
      option.className = "library-details__status-option";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = groupName;
      radio.value = value;
      if (ann.reading_status === value) radio.checked = true;
      option.appendChild(radio);
      const text = document.createElement("span");
      text.textContent = scholarT(label);
      option.appendChild(text);
      statusGroup.appendChild(option);
    });
    panel.appendChild(statusGroup);

    const starsLabel = document.createElement("div");
    starsLabel.className = "library-details__label";
    starsLabel.textContent = scholarT("Importance");
    panel.appendChild(starsLabel);

    const starsRow = document.createElement("div");
    starsRow.className = "library-details__stars";
    let importance = typeof ann.importance === "number" ? ann.importance : 0;
    const starBtns = [];
    const paintStars = () => {
      // forEach index idx is 0-based: the first `importance` buttons fill.
      starBtns.forEach((btn, idx) => {
        btn.textContent = idx < importance ? "★" : "☆";
      });
    };
    for (let i = 1; i <= 5; i += 1) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "library-details__star";
      btn.setAttribute("aria-label", scholarT("Importance") + ` ${i}`);
      btn.addEventListener("click", () => {
        // Clicking the current rating clears it (0 = unrated).
        importance = importance === i ? 0 : i;
        paintStars();
      });
      starBtns.push(btn);
      starsRow.appendChild(btn);
    }
    paintStars();
    panel.appendChild(starsRow);

    const tagsLabel = document.createElement("div");
    tagsLabel.className = "library-details__label";
    tagsLabel.textContent = scholarT("Tags");
    panel.appendChild(tagsLabel);
    const tagsInput = document.createElement("input");
    tagsInput.type = "text";
    tagsInput.className = "form-input library-details__tags";
    tagsInput.id = "details-tags";
    tagsInput.placeholder = scholarT("Add tag...");
    tagsInput.value = (ann.tags || []).join(", ");
    panel.appendChild(tagsInput);

    const notesLabel = document.createElement("div");
    notesLabel.className = "library-details__label";
    notesLabel.textContent = scholarT("Personal notes");
    panel.appendChild(notesLabel);
    const notesInput = document.createElement("textarea");
    notesInput.className = "form-input library-details__notes";
    notesInput.id = "details-notes";
    notesInput.rows = 4;
    notesInput.placeholder = scholarT("Add your notes about this paper...");
    notesInput.value = ann.notes || "";
    panel.appendChild(notesInput);

    const saveRow = document.createElement("div");
    saveRow.className = "library-details__actions";
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn-control-library";
    saveBtn.textContent = scholarT("Save changes");
    const saveMsg = document.createElement("span");
    saveMsg.className = "library-details__status";
    saveMsg.setAttribute("role", "status");
    saveBtn.addEventListener("click", async () => {
      saveMsg.textContent = "";
      const picked = statusGroup.querySelector("input:checked");
      const payload = { library_id: paper.paper_id };
      if (picked) payload.reading_status = picked.value;
      payload.importance = importance;
      payload.tags = tagsInput.value
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t);
      payload.notes = notesInput.value;
      saveBtn.disabled = true;
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/annotate`, {
          method: "POST",
          headers: csrfJsonHeaders(),
          body: JSON.stringify(payload),
        });
        const data = await readJson(resp);
        if (!resp.ok) throw new Error(data.error || scholarT("Save failed"));
        paper.annotations = data.annotations || {};
        renderBadges(badgesEl, paper);
        saveMsg.textContent = scholarT("Saved");
      } catch (err) {
        saveMsg.textContent = `${scholarT("Save failed")}: ${err.message}`;
      } finally {
        saveBtn.disabled = false;
      }
    });
    saveRow.appendChild(saveBtn);
    saveRow.appendChild(saveMsg);
    panel.appendChild(saveRow);

    // Slice 11: per-paper OA PDF download (hub library PDF actions).
    const pdfRow = document.createElement("div");
    pdfRow.className = "library-details__actions";
    const pdfBtn = document.createElement("button");
    pdfBtn.type = "button";
    pdfBtn.className = "btn-control-library";
    pdfBtn.textContent = scholarT("Download PDF");
    const pdfMsg = document.createElement("span");
    pdfMsg.className = "library-details__status";
    pdfMsg.setAttribute("role", "status");
    pdfBtn.addEventListener("click", async () => {
      pdfMsg.textContent = "";
      pdfBtn.disabled = true;
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/download-pdfs`, {
          method: "POST",
          headers: csrfJsonHeaders(),
          body: JSON.stringify({ library_ids: [paper.paper_id] }),
        });
        const data = await readJson(resp);
        if (!resp.ok) throw new Error(data.error || scholarT("Download failed"));
        if ((data.downloaded || []).length) {
          pdfMsg.textContent = scholarT("PDF downloaded");
        } else {
          const first = (data.failed || [])[0] || {};
          pdfMsg.textContent = first.error || scholarT("Download failed");
        }
      } catch (err) {
        pdfMsg.textContent = `${scholarT("Download failed")}: ${err.message}`;
      } finally {
        pdfBtn.disabled = false;
      }
    });
    pdfRow.appendChild(pdfBtn);
    pdfRow.appendChild(pdfMsg);
    panel.appendChild(pdfRow);

    // Slice 10: remove-from-library (hub details parity). Guarded by a
    // confirm -- hub deletes directly, but an undeleteable file tree
    // deserves one explicit gate.
    const dangerRow = document.createElement("div");
    dangerRow.className = "library-details__actions";
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn-control-library library-details__remove";
    removeBtn.textContent = scholarT("Remove from library");
    removeBtn.addEventListener("click", async () => {
      if (!window.confirm(scholarT("Remove this paper from the library?"))) return;
      removeBtn.disabled = true;
      try {
        const resp = await fetch(`${STX_MOUNT}/api/library/remove`, {
          method: "POST",
          headers: csrfJsonHeaders(),
          body: JSON.stringify({ library_id: paper.paper_id }),
        });
        const data = await readJson(resp);
        if (!resp.ok) throw new Error(data.error || scholarT("Remove failed"));
        lastRows = lastRows.filter((p) => p.paper_id !== paper.paper_id);
        renderRows();
      } catch (err) {
        saveMsg.textContent = `${scholarT("Remove failed")}: ${err.message}`;
      } finally {
        removeBtn.disabled = false;
      }
    });
    dangerRow.appendChild(removeBtn);
    panel.appendChild(dangerRow);
    return panel;
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
      const data = await readJson(resp);
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
      const data = await readJson(resp);
      if (!resp.ok) throw new Error(data.error || `Library load failed (${resp.status})`);
      hide(loadingEl);
      listEl.replaceChildren();
      const papers = data.papers || [];
      if (statsEl) {
        const n = papers.length;
        statsEl.textContent = data.filtered
          ? scholarT("%(count)s of %(total)s Papers", { count: n, total: data.total })
          : n + " " + scholarT(n === 1 ? "Paper" : "Papers");
        // Details strip: the Library section mirrors the list counts.
        // The project selection itself lives in the header picker
        // (operator 2026-10-23: no selector in Details), so the strip
        // carries no project scope suffix.
        const stripSummary = document.getElementById("libraryStripSummary");
        if (stripSummary) {
          stripSummary.textContent = statsEl.textContent;
        }
      }
      if (!papers.length) {
        listEl.appendChild(emptyState(data));
      } else {
        lastRows = papers;
        renderRows();
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
        const ext = { bibtex: "bib", ris: "ris", endnote: "enw", csv: "csv" }[fmt] || "txt";
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
  // Slice 5 (old-direct unification): preview-before-save. The chosen file's
  // text is held here between the preview POST and the confirm POST.
  const importPreview = document.getElementById("libraryImportPreview");
  const importEntries = document.getElementById("libraryImportEntries");
  const importConfirmBtn = document.getElementById("libraryImportConfirm");
  const importCancelBtn = document.getElementById("libraryImportCancel");
  let pendingImportText = "";
  let pendingImportName = "";

  function importHeaders() {
    // CSRF: the mounted hub enables CsrfViewMiddleware, so the Import POST
    // must carry the token. Read it from the hidden input rendered by the
    // {% csrf_token %} tag (populated by the middleware when enabled;
    // empty/inert standalone).
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const csrf = csrfInput ? csrfInput.value : "";
    const headers = { "Content-Type": "application/x-www-form-urlencoded" };
    if (csrf) headers["X-CSRFToken"] = csrf;
    return headers;
  }

  function renderImportPreview(entries) {
    importEntries.replaceChildren();
    entries.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "library-import-preview__entry";
      const title = document.createElement("div");
      title.className = "library-import-preview__title";
      title.textContent = entry.title || scholarT("Untitled");
      row.appendChild(title);
      const meta = document.createElement("div");
      meta.className = "library-import-preview__meta";
      const bits = [];
      if ((entry.authors || []).length) bits.push(entry.authors.join(", "));
      if (entry.year) bits.push(String(entry.year));
      if (entry.doi) bits.push(entry.doi);
      meta.textContent = bits.join(" · ");
      row.appendChild(meta);
      if (entry.exists) {
        const flag = document.createElement("span");
        flag.className = "library-import-preview__exists";
        flag.textContent = scholarT("Already in library");
        row.appendChild(flag);
      }
      importEntries.appendChild(row);
    });
    show(importPreview);
  }

  function hideImportPreview() {
    hide(importPreview);
    if (importEntries) importEntries.replaceChildren();
    pendingImportText = "";
    pendingImportName = "";
    if (importFile) importFile.value = "";
  }

  async function confirmImport() {
    if (!pendingImportText) return;
    importConfirmBtn.disabled = true;
    setIoStatus(scholarT("Importing %(file)s…", { file: pendingImportName }));
    try {
      const params = new URLSearchParams({ format: "bibtex", bibtex: pendingImportText });
      const resp = await fetch(`${STX_MOUNT}/api/library/import`, {
        method: "POST",
        headers: importHeaders(),
        body: params.toString(),
      });
      const data = await readJson(resp);
      if (!resp.ok) throw new Error(data.error || `Import failed (${resp.status})`);
      // A dict keyed call, not a template literal: scholarT looks the string
      // up verbatim, so an interpolated literal could never match the
      // catalog and the JA page showed English here (review blocker 2).
      setIoStatus(
        scholarT(
          data.imported === 1
            ? "Imported %(n)s paper from %(file)s"
            : "Imported %(n)s papers from %(file)s",
          { n: data.imported, file: pendingImportName },
        ),
      );
      hideImportPreview();
      loadLibrary(true); // refresh the list to show the imported papers
    } catch (err) {
      setIoStatus(String(err.message || err), true);
    } finally {
      importConfirmBtn.disabled = false;
    }
  }

  if (importConfirmBtn) {
    importConfirmBtn.addEventListener("click", confirmImport);
  }
  if (importCancelBtn) {
    importCancelBtn.addEventListener("click", () => {
      hideImportPreview();
      setIoStatus("");
    });
  }
  if (importBtn && importFile) {
    importBtn.addEventListener("click", () => importFile.click());
    importFile.addEventListener("change", async () => {
      const file = importFile.files && importFile.files[0];
      if (!file) return;
      importBtn.disabled = true;
      hideImportPreview();
      setIoStatus(scholarT("Previewing %(file)s…", { file: file.name }));
      try {
        const text = await file.text();
        const params = new URLSearchParams({ format: "bibtex", bibtex: text, preview: "1" });
        const resp = await fetch(`${STX_MOUNT}/api/library/import`, {
          method: "POST",
          headers: importHeaders(),
          body: params.toString(),
        });
        const data = await readJson(resp);
        if (!resp.ok) throw new Error(data.error || `Import failed (${resp.status})`);
        pendingImportText = text;
        pendingImportName = file.name;
        renderImportPreview(data.entries || []);
        setIoStatus(
          scholarT(
            (data.entries || []).length === 1
              ? "Previewing %(n)s paper from %(file)s"
              : "Previewing %(n)s papers from %(file)s",
            { n: (data.entries || []).length, file: file.name },
          ),
        );
      } catch (err) {
        setIoStatus(String(err.message || err), true);
        importFile.value = "";
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
  const libTabBtn = document.querySelector(
    '.stx-content-tabs__tab[aria-controls="tab-library"]',
  );
  if (libTabBtn) {
    libTabBtn.addEventListener("click", () => {
      if (!loaded) loadLibrary();
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
    checkExtStatuses();
  }
});
