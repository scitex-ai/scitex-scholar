/**
 * CitationGraphManager - Main controller for citation graph visualization
 *
 * Handles form submission, graph rendering, zoom/pan, tooltips, node selection.
 * Ported from scitex-cloud (standalone, no ES6 modules).
 *
 * Depends on: ForceSimulation.js, GraphRenderer.js (loaded before this).
 */
class CitationGraphManager {
  // Operator 2026-10-23: seed-only tab -- one fixed graph width, no
  // topN select, no DOI input. Matches the old-direct default (20).
  static DEFAULT_TOP_N = 20;

  constructor() {
    this.currentData = null;
    this.transform = { x: 0, y: 0, k: 1 };
    this.isDragging = false;
    this.selectedNode = null;
    // Error fallback (UX standard): the build the error box retries.
    this.lastBuild = null;
    // Set once the Citation Graph tab has asked the backend (see
    // bindLazyHealthProbe) so the live probe runs at most once per page.
    this.probed = false;

    this.renderer = new GraphRenderer({
      onNodeHover: (node, el) => this.showNodeTooltip(node, el),
      onNodeLeave: () => this.hideNodeTooltip(),
      onNodeClick: (node) => this.selectNode(node),
      onNodeDragStart: (e, node) => this.startNodeDrag(e, node),
    });

    this.init();
  }

  init() {
    this.bindEvents();
    // Operator 2026-10-23: cross-tab seed requests from Search results
    // arrive as one-shot scholar:build-graph events and build directly
    // at the fixed width. Brief-05: the event also carries { dois: [] }
    // for multi-seed networks (bulk Graph pill in Search).
    document.addEventListener("scholar:build-graph", (event) => {
      const dois = event.detail?.dois;
      if (Array.isArray(dois) && dois.length) {
        this.buildGraphMulti(dois.filter((d) => d).slice(0, 20));
        return;
      }
      const doi = event.detail?.doi;
      if (!doi) return;
      this.buildGraph(doi, CitationGraphManager.DEFAULT_TOP_N);
    });
    this.bindGraphLibrary();
    // CONFIGURATION ONLY on the initial-load path: no network call, so an
    // unconfigured or unreachable optional backend cannot delay the page or
    // emit a failing same-origin request. The live probe runs when the user
    // actually opens the Citation Graph tab.
    this.checkServiceHealth(false);
    this.bindLazyHealthProbe();
  }

  /** Probe once, the first time the Citation Graph tab opens (however it
      opens: click, swipe, arrow key, or prefill jump). The single producer
      path is app.js activateTab; this module listens for that announcement
      instead of its own click clone, so the status resolves on arrival
      rather than only on one input modality. */
  bindLazyHealthProbe() {
    document.addEventListener("scholar:tab-activated", (event) => {
      if (event.detail?.tab !== "graph") return;
      if (this.probed) return;
      this.probed = true;
      this.checkServiceHealth(true);
      // Slice 3a (old-direct parity): the library-seed picker loads with
      // the same laziness -- no /api/library request for users who never
      // open the graph tab. The Graph Library list loads alongside it.
      this.loadLibrarySeed();
      this.loadSavedGraphs();
    });
  }

  bindEvents() {
    const resetBtn = document.getElementById("resetZoomBtn");
    if (resetBtn) resetBtn.addEventListener("click", () => this.resetView());

    // Old-direct U5: step zoom in/out (hub zoomInBtn/zoomOutBtn, factor
    // 1.4 about the view center). Same clamp as the wheel path.
    const zoomInBtn = document.getElementById("zoomInBtn");
    if (zoomInBtn) zoomInBtn.addEventListener("click", () => this.zoomStep(1.4));
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    if (zoomOutBtn) zoomOutBtn.addEventListener("click", () => this.zoomStep(1 / 1.4));

    const downloadBtn = document.getElementById("downloadSvgBtn");
    if (downloadBtn)
      downloadBtn.addEventListener("click", () => this.downloadSvg());

    // Old-direct U6: PNG sibling of the SVG download (hub downloadPngBtn).
    const pngBtn = document.getElementById("downloadPngBtn");
    if (pngBtn) pngBtn.addEventListener("click", () => this.downloadPng());

    const fitBtn = document.getElementById("fitViewBtn");
    if (fitBtn) fitBtn.addEventListener("click", () => this.fitToView());

    // Old-direct U7: Esc closes the node sheet from anywhere and
    // returns focus to the invoking node (same path as the × button).
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const panel = document.getElementById("nodeDetailsPanel");
      if (panel && !panel.classList.contains("hidden")) this.hideNodeDetails();
    });

    // Error fallback (UX standard): retry re-runs the failed build with the
    // same seed -- the error box retries, not just dismisses.
    const retryBtn = document.getElementById("graphRetryBtn");
    if (retryBtn) {
      retryBtn.addEventListener("click", () => {
        if (this.lastBuild) this.buildGraph(this.lastBuild.doi, this.lastBuild.topN);
      });
    }
  }

  async checkServiceHealth(probe) {
    const el = document.getElementById("serviceStatus");
    if (!el) return;

    // Render helper: a status dot + label, and (when limited) the explanation
    // of what is limited and what the user can DO. The health endpoint returns
    // {status, error, detail, fix}; `detail`/`fix` are the answer, `error` the
    // one-line label (item 150-152, hub live audit 2026-09-14). The strip's
    // graph LED mirrors the same state (old Sources style: dots + expand).
    const set = (cls, label, detail, fix, led) => {
      let html =
        '<span class="status-indicator ' + cls + '">&#9679; ' + label + "</span>";
      if (detail) html += '<small class="status-detail">' + detail + "</small>";
      if (fix) html += '<small class="status-fix">' + fix + "</small>";
      el.innerHTML = html;
      const dot = document.querySelector('.status-led[data-source="graph"]');
      if (dot) {
        dot.dataset.status = led;
        dot.title = label;
      }
    };

    // `probe` is the ONLY difference between the initial-load report and the
    // live check: the tab probe asks the backend, the initial load asks the
    // configuration. Same states, same UI.
    const url = STX_MOUNT + "/api/graph/health" + (probe ? "?probe=1" : "");

    try {
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.status === "healthy") {
        set("status-healthy", scholarT("Service available"), undefined, undefined, "ready");
      } else if (data.status === "degraded") {
        set("status-warning", data.error || scholarT("Service limited"), data.detail, data.fix, "limited");
      } else if (data.status === "configured") {
        // Endpoint present, not probed yet — deliberately NOT "available":
        // claiming ready before the backend answered is the failure this
        // endpoint exists to avoid.
        set(
          "status-checking",
          data.error || scholarT("Not checked yet"),
          data.detail,
          data.fix,
          "checking",
        );
      } else if (data.status === "unconfigured") {
        set(
          "status-warning",
          data.error || scholarT("Service limited"),
          data.detail,
          data.fix,
          "limited",
        );
      } else {
        set("status-error", data.error || scholarT("Service unavailable"), data.detail, data.fix, "unavailable");
      }
    } catch {
      // The report itself could not be read — a genuine failure, reported as
      // unavailable rather than as limited or ready.
      set("status-error", scholarT("Service unavailable"), undefined, undefined, "error");
    }
  }

  /**
   * Slice 3a (old-direct parity): seed-from-library picker. Lists library
   * papers carrying a DOI from the EXISTING /api/library endpoint; clicking
   * one seeds the build directly (hub _GraphInputHandler: "Build graph
   * directly from library-selected DOI"). No new backend.
   */
  async loadLibrarySeed() {
    const box = document.getElementById("graphLibrarySeed");
    if (!box || box.dataset.loaded === "1") return;
    box.setAttribute("aria-label", scholarT("Seed from your Library"));
    box.innerHTML =
      '<p class="empty-message">' + this.esc(scholarT("Loading your library…")) + "</p>";
    try {
      const resp = await fetch(STX_MOUNT + "/api/library");
      if (!resp.ok) throw new Error("Failed");
      const data = await resp.json();
      const seeds = (data.papers || []).filter((p) => p && p.doi);
      if (seeds.length === 0) {
        box.innerHTML =
          '<p class="empty-message">' +
          this.esc(scholarT("No papers with a DOI in your library yet.")) +
          "</p>";
        box.dataset.loaded = "1";
        return;
      }
      box.innerHTML = seeds
        .map(
          (p) =>
            '<div class="graph-library-seed__item" data-doi="' +
            this.esc(p.doi) +
            '">' +
            '<div class="graph-library-seed__title">' +
            this.esc(p.title || scholarT("Untitled")) +
            "</div>" +
            '<div class="graph-library-seed__meta">' +
            this.esc((p.authors || []).slice(0, 2).join(", ")) +
            (p.year ? " (" + this.esc(p.year) + ")" : "") +
            "</div>" +
            "</div>",
        )
        .join("");
      box.querySelectorAll(".graph-library-seed__item").forEach((item) => {
        item.addEventListener("click", () => {
          const doi = item.getAttribute("data-doi");
          if (!doi) return;
          // Operator 2026-10-23: seed-only tab -- the selection builds
          // directly at the fixed graph width. No DOI typing, no topN.
          this.buildGraph(doi, CitationGraphManager.DEFAULT_TOP_N);
        });
      });
      box.dataset.loaded = "1";
    } catch {
      // Error fallback (UX standard): the seed list is auxiliary, but its
      // failure still retries in place instead of sitting dead.
      box.innerHTML =
        '<p class="error-message">' +
        this.esc(scholarT("Service unavailable")) +
        "</p>" +
        '<button type="button" class="btn-control-library" data-seed-retry="1">' +
        this.esc(scholarT("Retry")) +
        "</button>";
      const seedRetry = box.querySelector("[data-seed-retry]");
      if (seedRetry) {
        seedRetry.addEventListener("click", () => this.loadLibrarySeed());
      }
    }
  }

  async buildGraph(doi, topN) {
    this.lastBuild = { doi, topN };
    this.showLoading(true);
    this.hideError();

    try {
      const url = `${STX_MOUNT}/api/graph/network?doi=${encodeURIComponent(doi)}&top_n=${topN}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Failed to build network");
      }

      const data = await resp.json();
      this.currentData = data;
      this.renderGraph(data);
      this.renderRelatedFromGraph(topN);
    } catch (err) {
      this.showError(err.message || "An error occurred", true);
    } finally {
      this.showLoading(false);
    }
  }

  // Brief-05: multi-seed network from checked Search works
  // (api/graph/network/multi, at most 20 seeds). Saves capture the
  // primary seed only -- the save button stays armed for single-seed
  // builds (see bindGraphLibrary).
  async buildGraphMulti(dois) {
    this.lastBuild = { dois: dois.slice(), topN: null };
    this.showLoading(true);
    this.hideError();

    try {
      const url =
        `${STX_MOUNT}/api/graph/network/multi?dois=` +
        dois.map(encodeURIComponent).join(",") +
        "&num_related_per_doi=20";
      const resp = await fetch(url);
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error || "Failed to build network");
      }

      const data = await resp.json();
      this.currentData = data;
      this.renderGraph(data);
      this.renderRelatedFromGraph(CitationGraphManager.DEFAULT_TOP_N);
    } catch (err) {
      this.showError(err.message || "An error occurred", true);
    } finally {
      this.showLoading(false);
    }
  }

  // Brief-05: Graph Library CRUD over the thin api/graphs/* endpoints
  // (1.24.0). The file stays authoritative server-side; the store is
  // the derived mirror -- the client only ever sees merged rows.
  csrfJsonHeaders() {
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const headers = { "Content-Type": "application/json" };
    if (csrfInput && csrfInput.value) headers["X-CSRFToken"] = csrfInput.value;
    return headers;
  }

  setLibraryStatus(msg, isErr) {
    const el = document.getElementById("graphLibraryStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("library-io__status--error", !!isErr);
  }

  bindGraphLibrary() {
    const saveBtn = document.getElementById("graphSaveBtn");
    if (saveBtn) saveBtn.addEventListener("click", () => this.saveCurrentGraph());
    const nameInput = document.getElementById("graphSaveName");
    if (nameInput) {
      nameInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.saveCurrentGraph();
        }
      });
    }
  }

  async loadSavedGraphs() {
    const list = document.getElementById("graphSavedList");
    const count = document.getElementById("graphLibraryCount");
    if (!list) return;
    try {
      const resp = await fetch(STX_MOUNT + "/api/graphs/list");
      if (!resp.ok) throw new Error("Failed");
      const data = await resp.json();
      this.renderSavedGraphs(data.graphs || []);
      if (count) {
        const n = (data.graphs || []).length;
        count.textContent = n ? scholarT("%(n)s saved", { n }) : "";
      }
    } catch {
      list.innerHTML =
        '<p class="empty-message">' +
        this.esc(scholarT("Service unavailable")) +
        "</p>";
    }
  }

  renderSavedGraphs(graphs) {
    const list = document.getElementById("graphSavedList");
    if (!list) return;
    if (!graphs.length) {
      list.innerHTML =
        '<p class="empty-message">' +
        this.esc(scholarT("No saved graphs yet.")) +
        "</p>";
      return;
    }
    list.replaceChildren();
    graphs.forEach((g) => {
      const item = document.createElement("div");
      item.className = "library-item";

      const main = document.createElement("div");
      main.className = "library-item__main";
      const title = document.createElement("div");
      title.className = "library-item__title";
      title.textContent = g.name || scholarT("Untitled");
      main.appendChild(title);
      const meta = document.createElement("div");
      meta.className = "library-item__meta";
      const seed = document.createElement("span");
      seed.textContent = g.seed_doi || "";
      meta.appendChild(seed);
      if (g.created_at) {
        const when = document.createElement("span");
        when.textContent = String(g.created_at).slice(0, 10);
        meta.appendChild(when);
      }
      main.appendChild(meta);
      item.appendChild(main);

      const actions = document.createElement("div");
      actions.className = "library-item__actions";
      const loadBtn = document.createElement("button");
      loadBtn.type = "button";
      loadBtn.className = "btn-control-library";
      loadBtn.textContent = scholarT("Load");
      loadBtn.addEventListener("click", () => {
        if (g.seed_doi) this.buildGraph(g.seed_doi, CitationGraphManager.DEFAULT_TOP_N);
      });
      actions.appendChild(loadBtn);
      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "btn-control-library";
      renameBtn.textContent = scholarT("Rename");
      renameBtn.addEventListener("click", () => this.startRename(item, g));
      actions.appendChild(renameBtn);
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn-control-library";
      deleteBtn.textContent = scholarT("Delete");
      deleteBtn.addEventListener("click", () => this.armDelete(deleteBtn, g));
      actions.appendChild(deleteBtn);
      item.appendChild(actions);

      list.appendChild(item);
    });
  }

  async saveCurrentGraph() {
    const nameInput = document.getElementById("graphSaveName");
    const name = (nameInput ? nameInput.value : "").trim();
    if (!name) {
      this.setLibraryStatus(scholarT("Name the graph and build it first."), true);
      return;
    }
    const seed = this.lastBuild && this.lastBuild.doi;
    if (!seed) {
      this.setLibraryStatus(scholarT("Build a single-seed graph first."), true);
      return;
    }
    try {
      const resp = await fetch(STX_MOUNT + "/api/graphs/save", {
        method: "POST",
        headers: this.csrfJsonHeaders(),
        body: JSON.stringify({ name, seed_doi: seed }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed");
      if (nameInput) nameInput.value = "";
      this.setLibraryStatus(scholarT("Graph saved"), false);
      await this.loadSavedGraphs();
    } catch (err) {
      this.setLibraryStatus(err.message || scholarT("Save failed"), true);
    }
  }

  startRename(item, g) {
    const title = item.querySelector(".library-item__title");
    if (!title || item.querySelector(".graph-rename-input")) return;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "form-input graph-rename-input";
    input.value = g.name || "";
    input.setAttribute("aria-label", scholarT("Rename"));
    title.replaceChildren(input);
    input.focus();
    input.select();
    const commit = async (saveIt) => {
      const next = input.value.trim();
      title.textContent = saveIt && next ? next : g.name || scholarT("Untitled");
      if (!saveIt || !next || next === g.name) return;
      try {
        const resp = await fetch(STX_MOUNT + "/api/graphs/rename", {
          method: "POST",
          headers: this.csrfJsonHeaders(),
          body: JSON.stringify({ id: g.id, name: next }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "Failed");
        g.name = next;
        title.textContent = next;
        this.setLibraryStatus(scholarT("Graph renamed"), false);
      } catch (err) {
        this.setLibraryStatus(err.message || scholarT("Save failed"), true);
      }
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        commit(true);
      } else if (e.key === "Escape") {
        commit(false);
      }
    });
    input.addEventListener("blur", () => commit(true));
  }

  armDelete(deleteBtn, g) {
    if (deleteBtn.dataset.armed === "1") {
      this.deleteSavedGraph(g, deleteBtn);
      return;
    }
    deleteBtn.dataset.armed = "1";
    deleteBtn.textContent = scholarT("Confirm delete?");
    const disarm = () => {
      deleteBtn.dataset.armed = "";
      deleteBtn.textContent = scholarT("Delete");
    };
    deleteBtn.addEventListener("blur", disarm, { once: true });
    setTimeout(() => {
      if (deleteBtn.dataset.armed === "1") disarm();
    }, 4000);
  }

  async deleteSavedGraph(g, deleteBtn) {
    try {
      const resp = await fetch(STX_MOUNT + "/api/graphs/delete", {
        method: "POST",
        headers: this.csrfJsonHeaders(),
        body: JSON.stringify({ id: g.id }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Failed");
      this.setLibraryStatus(scholarT("Graph deleted"), false);
      await this.loadSavedGraphs();
    } catch (err) {
      this.setLibraryStatus(err.message || scholarT("Save failed"), true);
      if (deleteBtn) {
        deleteBtn.dataset.armed = "";
        deleteBtn.textContent = scholarT("Delete");
      }
    }
  }

  renderGraph(data) {
    const container = document.getElementById("graphVisualization");
    const canvas = document.getElementById("graphCanvas");
    if (!container || !canvas) return;

    container.classList.remove("hidden");

    const titleEl = document.getElementById("graphTitle");
    if (titleEl) {
      const seed = data.nodes.find((n) => n.is_seed);
      titleEl.textContent = seed
        ? "Network: " + seed.title.substring(0, 60) + "..."
        : "Citation Network";
    }

    const statsEl = document.getElementById("graphStats");
    if (statsEl) {
      statsEl.textContent = `${data.nodes.length} nodes, ${data.edges.length} edges`;
    }
    // Details strip (operator 2026-10-22): the graph section mirrors the
    // build counts next to the controls.
    const stripSummary = document.getElementById("graphStripSummary");
    if (stripSummary) {
      stripSummary.textContent = `${data.nodes.length} nodes, ${data.edges.length} edges`;
    }

    this.renderer.render(canvas, data.nodes, data.edges);
    this.setupZoomPan(canvas);
  }

  setupZoomPan(container) {
    const svg = this.renderer.getSvg();
    if (!svg) return;

    let isPanning = false;
    let startX = 0;
    let startY = 0;

    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const rect = svg.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const newK = Math.max(0.1, Math.min(5, this.transform.k * factor));
      this.transform.x =
        mx - (mx - this.transform.x) * (newK / this.transform.k);
      this.transform.y =
        my - (my - this.transform.y) * (newK / this.transform.k);
      this.transform.k = newK;
      this.renderer.applyTransform(this.transform);
    });

    svg.addEventListener("mousedown", (e) => {
      if (e.target === svg || e.target.closest(".graph-edges")) {
        isPanning = true;
        startX = e.clientX - this.transform.x;
        startY = e.clientY - this.transform.y;
        svg.style.cursor = "grabbing";
      }
    });

    svg.addEventListener("mousemove", (e) => {
      if (isPanning && !this.isDragging) {
        this.transform.x = e.clientX - startX;
        this.transform.y = e.clientY - startY;
        this.renderer.applyTransform(this.transform);
      }
    });

    svg.addEventListener("mouseup", () => {
      isPanning = false;
      svg.style.cursor = "grab";
    });
    svg.addEventListener("mouseleave", () => {
      isPanning = false;
      svg.style.cursor = "grab";
    });
    svg.style.cursor = "grab";
  }

  startNodeDrag(e, node) {
    e.stopPropagation();
    this.isDragging = true;
    const svg = this.renderer.getSvg();
    const rect = svg.getBoundingClientRect();

    const onMove = (ev) => {
      const x = (ev.clientX - rect.left - this.transform.x) / this.transform.k;
      const y = (ev.clientY - rect.top - this.transform.y) / this.transform.k;
      node.fx = x;
      node.fy = y;
      node.x = x;
      node.y = y;
      const sim = this.renderer.getSimulation();
      if (sim) sim.reheat();
    };

    const onUp = () => {
      this.isDragging = false;
      if (!node.is_seed) {
        node.fx = null;
        node.fy = null;
      }
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  showNodeTooltip(node, element) {
    const old = document.getElementById("graphTooltip");
    if (old) old.remove();

    const tip = document.createElement("div");
    tip.id = "graphTooltip";
    tip.className = "graph-tooltip";
    tip.innerHTML = `
      <div class="tooltip-title">${this.esc(node.title)}</div>
      <div class="tooltip-authors">${this.esc((node.authors || []).slice(0, 3).join(", "))}${(node.authors || []).length > 3 ? "..." : ""}</div>
      <div class="tooltip-meta">
        <span class="tooltip-year">${this.esc(node.year || "?")}</span>
        ${node.similarity_score ? '<span class="tooltip-score">Score: ' + node.similarity_score.toFixed(1) + "</span>" : ""}
      </div>
      <div class="tooltip-hint">Click to view details</div>
    `;
    document.body.appendChild(tip);

    const rect = element.getBoundingClientRect();
    tip.style.left = rect.left + rect.width / 2 + "px";
    tip.style.top = rect.top - 10 + "px";
  }

  hideNodeTooltip() {
    const el = document.getElementById("graphTooltip");
    if (el) el.remove();
  }

  selectNode(node) {
    this.selectedNode = node;
    document
      .querySelectorAll(".graph-node")
      .forEach((el) => el.classList.remove("selected"));
    const el = document.querySelector(`[data-id="${CSS.escape(node.id)}"]`);
    // Old-direct U7: the invoking node is the focus-return target when
    // the sheet closes, so it must be focusable.
    if (el) {
      el.classList.add("selected");
      el.setAttribute("tabindex", "-1");
      this.lastSelectedEl = el;
    }
    this.showNodeDetails(node);
  }

  // Old-direct U7: hide the sheet and return focus to the invoking node
  // (or the graph canvas when the node is gone). Esc calls this too.
  hideNodeDetails() {
    const panel = document.getElementById("nodeDetailsPanel");
    if (panel) panel.classList.add("hidden");
    const target =
      this.lastSelectedEl && document.contains(this.lastSelectedEl)
        ? this.lastSelectedEl
        : document.getElementById("graphCanvas");
    if (target && typeof target.focus === "function") target.focus({ preventScroll: true });
  }

  showNodeDetails(node) {
    const panel = document.getElementById("nodeDetailsPanel");
    if (!panel) return;
    panel.classList.remove("hidden");
    // Already-loaded graph_data only: journal + citation count join the
    // existing title/meta/DOI (hub sheet shape). Values render through
    // this.esc -- node metadata is third-party data.
    const meta = [node.year || "?", node.journal || ""].filter(Boolean).join(" · ");
    panel.innerHTML = `
      <div class="node-details-header">
        <h6>${node.is_seed ? "&#9733; Seed Paper" : "Related Paper"}</h6>
        <button type="button" class="btn-close-panel" data-act="close" aria-label="${this.esc(scholarT("Close"))}">&times;</button>
      </div>
      <div class="node-details-content">
        <div class="detail-title">${this.esc(node.title)}</div>
        <div class="detail-authors">${this.esc((node.authors || []).join(", "))}</div>
        <div class="detail-year">${this.esc(meta)}</div>
        ${node.citation_count != null ? `<div class="detail-cites">${this.esc(Number(node.citation_count).toLocaleString())} ${this.esc(scholarT("citations"))}</div>` : ""}
        ${node.similarity_score ? '<div class="detail-score">Similarity: <strong>' + node.similarity_score.toFixed(2) + "</strong></div>" : ""}
        <div class="detail-doi"><a href="https://doi.org/${encodeURIComponent(node.id)}" target="_blank" rel="noopener">View on DOI.org &#8599;</a></div>
        <div class="detail-actions">
          <button type="button" class="btn-control-library" data-act="add">${this.esc(scholarT("Add to library"))}</button>
          ${node.is_seed ? "" : `<button type="button" class="btn-control-library" data-act="explore">${this.esc(scholarT("Explore from here"))}</button>`}
        </div>
      </div>
    `;
    const closeBtn = panel.querySelector('[data-act="close"]');
    if (closeBtn) closeBtn.addEventListener("click", () => this.hideNodeDetails());
    const addBtn = panel.querySelector('[data-act="add"]');
    if (addBtn) addBtn.addEventListener("click", () => this.addToLibrary(node, addBtn));
    const exploreBtn = panel.querySelector('[data-act="explore"]');
    if (exploreBtn) exploreBtn.addEventListener("click", () => this.exploreFromHere(node));
  }

  // Catch-up: hub NodeSheet actions over already-loaded node metadata.
  // Add persists through the existing single-save endpoint (same payload
  // shape as the search surface); explore rebuilds from the node DOI.
  async addToLibrary(node, btn) {
    btn.disabled = true;
    try {
      const resp = await fetch(`${STX_MOUNT}/api/library/save`, {
        method: "POST",
        headers: this.csrfJsonHeaders(),
        body: JSON.stringify({
          title: node.title || "",
          authors: node.authors || [],
          year: node.year || null,
          venue: node.journal || "",
          doi: node.id || "",
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error || scholarT("Save failed"));
      btn.textContent = scholarT("Saved");
    } catch (err) {
      btn.textContent = scholarT("Save failed");
      btn.disabled = false;
    }
  }

  exploreFromHere(node) {
    if (!node || !node.id) return;
    this.hideNodeDetails();
    this.buildGraph(node.id, CitationGraphManager.DEFAULT_TOP_N);
  }

  // Catch-up: the related list derives from the DRAWN graph data (hub
  // parity: same NetworkData nodes, no second fetch, never disagrees
  // with the viz). Seeds first, then citation count -- hub order.
  // Empty graph gets guidance, not a bare canvas.
  renderRelatedFromGraph(limit) {
    const container = document.getElementById("relatedPapersList");
    const content = document.getElementById("relatedPapersContent");
    if (!container || !content) return;
    const nodes = (this.currentData && this.currentData.nodes) || [];
    if (!nodes.length) {
      content.innerHTML =
        '<p class="empty-message" id="graphEmptyHint">No papers in this graph yet. Enter a DOI above and choose Build Graph to start.</p>';
      container.classList.remove("hidden");
      return;
    }
    const ranked = [...nodes].sort(
      (a, b) =>
        Number(b.is_seed || false) - Number(a.is_seed || false) ||
        (b.citation_count || 0) - (a.citation_count || 0),
    ).slice(0, Math.max(1, limit || nodes.length));

      content.innerHTML = ranked
      .map(
        (p, i) => `
            <div class="related-paper-item" data-doi="${this.esc(p.id)}">
              <div class="paper-rank">${i + 1}</div>
              <div class="paper-info">
                <div class="paper-title">${this.esc(p.title)}</div>
                <div class="paper-meta">
                  <span class="paper-authors">${this.esc((p.authors || []).slice(0, 2).join(", "))}${(p.authors || []).length > 2 ? " et al." : ""}</span>
                  <span class="paper-year">${this.esc(p.year || "?")}</span>
                </div>
              </div>
              <div class="paper-score">
                <div class="score-bar"><div class="score-fill" style="width: ${Math.min(100, (p.citation_count || 0))}%"></div></div>
                <span class="score-value">${this.esc(Number(p.citation_count || 0).toLocaleString())}</span>
              </div>
            </div>
          `,
      )
      .join("");

    content.querySelectorAll(".related-paper-item").forEach((item) => {
      item.addEventListener("click", () => {
        const d = item.getAttribute("data-doi");
        const n = (this.currentData.nodes || []).find((nd) => nd.id === d);
        if (n) this.selectNode(n);
      });
    });

    container.classList.remove("hidden");
  }

  showLoading(show) {
    const loading = document.getElementById("graphLoading");
    const viz = document.getElementById("graphVisualization");
    const related = document.getElementById("relatedPapersList");
    if (show) {
      if (loading) loading.classList.remove("hidden");
      if (viz) viz.classList.add("hidden");
      if (related) related.classList.add("hidden");
    } else {
      if (loading) loading.classList.add("hidden");
    }
  }

  showError(msg, canRetry) {
    const el = document.getElementById("graphError");
    const msgEl = document.getElementById("graphErrorMessage");
    const retryBtn = document.getElementById("graphRetryBtn");
    if (el && msgEl) {
      msgEl.textContent = msg;
      // Validation mistakes (empty DOI) carry no retry: the user must fix
      // the input by hand. Build failures do -- the seed is remembered.
      if (retryBtn) retryBtn.classList.toggle("hidden", !canRetry);
      el.classList.remove("hidden");
    }
  }

  hideError() {
    const el = document.getElementById("graphError");
    if (el) el.classList.add("hidden");
  }

  resetView() {
    this.transform = { x: 0, y: 0, k: 1 };
    this.renderer.applyTransform(this.transform);
  }

  // Old-direct U5: step zoom about the SVG center (hub zoomBy(1.4)).
  // Same 0.1-5 clamp as the wheel path; fit/reset are untouched.
  zoomStep(factor) {
    const svg = this.renderer.getSvg();
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = rect.width / 2;
    const my = rect.height / 2;
    const newK = Math.max(0.1, Math.min(5, this.transform.k * factor));
    this.transform.x =
      mx - (mx - this.transform.x) * (newK / this.transform.k);
    this.transform.y =
      my - (my - this.transform.y) * (newK / this.transform.k);
    this.transform.k = newK;
    this.renderer.applyTransform(this.transform);
  }

  fitToView() {
    if (!this.currentData) return;
    const svg = this.renderer.getSvg();
    if (!svg) return;

    const nodes = this.currentData.nodes;
    if (nodes.length === 0) return;

    const minX = Math.min(...nodes.map((n) => n.x || 0));
    const maxX = Math.max(...nodes.map((n) => n.x || 0));
    const minY = Math.min(...nodes.map((n) => n.y || 0));
    const maxY = Math.max(...nodes.map((n) => n.y || 0));

    const pad = 50;
    const gw = maxX - minX + pad * 2;
    const gh = maxY - minY + pad * 2;
    const svgRect = svg.getBoundingClientRect();
    const scale = Math.min(svgRect.width / gw, svgRect.height / gh, 2);

    this.transform = {
      x: svgRect.width / 2 - ((minX + maxX) / 2) * scale,
      y: svgRect.height / 2 - ((minY + maxY) / 2) * scale,
      k: scale,
    };
    this.renderer.applyTransform(this.transform);
  }

  downloadSvg() {
    const svg = document.getElementById("citationGraphSvg");
    if (!svg) return;

    const data = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([data], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "citation-graph.svg";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Old-direct U6: download the current view as PNG (hub downloadPngBtn).
  // The renderer is SVG, so rasterize client-side: serialize the live SVG,
  // paint it onto a 2x canvas (sharp on hidpi), and Blob-download the PNG.
  // No backend. Failures stay silent (console.warn) -- export must never
  // break the graph.
  downloadPng() {
    const svg = document.getElementById("citationGraphSvg");
    if (!svg) return;

    const data = new XMLSerializer().serializeToString(svg);
    const url = URL.createObjectURL(new Blob([data], { type: "image/svg+xml" }));
    const img = new Image();
    img.onload = () => {
      try {
        const width = svg.clientWidth || 800;
        const height = svg.clientHeight || 600;
        const canvas = document.createElement("canvas");
        canvas.width = width * 2;
        canvas.height = height * 2;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("no 2d context");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
          URL.revokeObjectURL(url);
          if (!blob) return;
          const pngUrl = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = pngUrl;
          a.download = "citation-graph.png";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(pngUrl);
        }, "image/png");
      } catch (err) {
        URL.revokeObjectURL(url);
        console.warn("graph PNG export unavailable:", err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      console.warn("graph PNG export unavailable: SVG image failed to load");
    };
    img.src = url;
  }

  /**
   * Slice 9 (old-direct unification): saved graphs. Hub's graph page
   * saves/loads/deletes graphs; the leaf backend ships the same endpoints
   * (parity slice 1) with no UI. Recipes rebuild from the seed DOI through
   * the existing network build -- no new backend.
   */
  csrfJsonHeaders() {
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const headers = { "Content-Type": "application/json" };
    if (csrfInput && csrfInput.value) headers["X-CSRFToken"] = csrfInput.value;
    return headers;
  }

  esc(text) {
    const d = document.createElement("div");
    d.textContent = text || "";
    return d.innerHTML;
  }
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  new CitationGraphManager();
});
