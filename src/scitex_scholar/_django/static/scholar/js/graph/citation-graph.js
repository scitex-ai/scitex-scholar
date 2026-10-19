/**
 * CitationGraphManager - Main controller for citation graph visualization
 *
 * Handles form submission, graph rendering, zoom/pan, tooltips, node selection.
 * Ported from scitex-cloud (standalone, no ES6 modules).
 *
 * Depends on: ForceSimulation.js, GraphRenderer.js (loaded before this).
 */
class CitationGraphManager {
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
    // CONFIGURATION ONLY on the initial-load path: no network call, so an
    // unconfigured or unreachable optional backend cannot delay the page or
    // emit a failing same-origin request. The live probe runs when the user
    // actually opens the Citation Graph tab.
    this.checkServiceHealth(false);
    this.bindLazyHealthProbe();
  }

  /** Probe once, the first time the Citation Graph tab is opened. */
  bindLazyHealthProbe() {
    const graphTab = document.querySelector(
      '.stx-content-tabs__tab[aria-controls="tab-graph"]',
    );
    if (!graphTab) return;
    graphTab.addEventListener("click", () => {
      if (this.probed) return;
      this.probed = true;
      this.checkServiceHealth(true);
      // Slice 3a (old-direct parity): the library-seed picker loads with
      // the same laziness -- no /api/library request for users who never
      // open the graph tab.
      this.loadLibrarySeed();
    });
  }

  bindEvents() {
    const form = document.getElementById("graphForm");
    if (form) form.addEventListener("submit", (e) => this.handleSubmit(e));

    const resetBtn = document.getElementById("resetZoomBtn");
    if (resetBtn) resetBtn.addEventListener("click", () => this.resetView());

    const downloadBtn = document.getElementById("downloadSvgBtn");
    if (downloadBtn)
      downloadBtn.addEventListener("click", () => this.downloadSvg());

    const fitBtn = document.getElementById("fitViewBtn");
    if (fitBtn) fitBtn.addEventListener("click", () => this.fitToView());

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

  async handleSubmit(e) {
    e.preventDefault();
    const doiInput = document.getElementById("doiInput");
    const topNSelect = document.getElementById("topN");
    if (!doiInput || !doiInput.value.trim()) {
      this.showError("Please enter a DOI");
      return;
    }

    const doi = doiInput.value.trim();
    const topN = parseInt(topNSelect ? topNSelect.value : "20", 10);
    this.buildGraph(doi, topN);
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
          const doiInput = document.getElementById("doiInput");
          if (doiInput) doiInput.value = doi;
          const topNSelect = document.getElementById("topN");
          const topN = parseInt(topNSelect ? topNSelect.value : "20", 10);
          this.buildGraph(doi, topN);
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
      this.fetchRelatedPapers(doi, topN);
    } catch (err) {
      this.showError(err.message || "An error occurred", true);
    } finally {
      this.showLoading(false);
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
    if (el) el.classList.add("selected");
    this.showNodeDetails(node);
  }

  showNodeDetails(node) {
    const panel = document.getElementById("nodeDetailsPanel");
    if (!panel) return;
    panel.classList.remove("hidden");
    panel.innerHTML = `
      <div class="node-details-header">
        <h6>${node.is_seed ? "&#9733; Seed Paper" : "Related Paper"}</h6>
        <button class="btn-close-panel" onclick="document.getElementById('nodeDetailsPanel').classList.add('hidden')">&times;</button>
      </div>
      <div class="node-details-content">
        <div class="detail-title">${this.esc(node.title)}</div>
        <div class="detail-authors">${this.esc((node.authors || []).join(", "))}</div>
        <div class="detail-year">Published: ${this.esc(node.year || "?")}</div>
        ${node.similarity_score ? '<div class="detail-score">Similarity: <strong>' + node.similarity_score.toFixed(2) + "</strong></div>" : ""}
        <div class="detail-doi"><a href="https://doi.org/${encodeURIComponent(node.id)}" target="_blank" rel="noopener">View on DOI.org &#8599;</a></div>
      </div>
    `;
  }

  async fetchRelatedPapers(doi, limit) {
    const container = document.getElementById("relatedPapersList");
    const content = document.getElementById("relatedPapersContent");
    if (!container || !content) return;

    try {
      const url = `${STX_MOUNT}/api/graph/related?doi=${encodeURIComponent(doi)}&limit=${limit}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error("Failed");

      const data = await resp.json();
      const papers = data.related || [];

      content.innerHTML =
        papers.length === 0
          ? '<p class="empty-message">No related papers found</p>'
          : papers
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
                <div class="score-bar"><div class="score-fill" style="width: ${Math.min(100, (p.similarity_score || 0) * 2)}%"></div></div>
                <span class="score-value">${(p.similarity_score || 0).toFixed(1)}</span>
              </div>
            </div>
          `,
              )
              .join("");

      content.querySelectorAll(".related-paper-item").forEach((item) => {
        item.addEventListener("click", () => {
          const d = item.getAttribute("data-doi");
          if (d && this.currentData) {
            const n = this.currentData.nodes.find((nd) => nd.id === d);
            if (n) this.selectNode(n);
          }
        });
      });

      container.classList.remove("hidden");
    } catch {
      content.innerHTML =
        '<p class="error-message">Failed to load related papers</p>';
      container.classList.remove("hidden");
    }
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
