/**
 * Scholar GUI - Tab Manager
 *
 * Manages tab switching for the Scholar SPA.
 *
 * COMPASS 2026-09-10 (L316): when the active tab changes, also show or hide
 * the sidebar "Graph Controls" hint (it only applies to the Citation Graph
 * tab) so the sidebar does not present controls for a surface that is not
 * visible. The tab bar itself is unchanged: every tab keeps the same
 * min-height and the panels share the same container, so nothing jumps
 * horizontally on switch.
 */
const initializedRoots = new WeakSet();

function initScholarTabs(root) {
  if (initializedRoots.has(root)) return;
  initializedRoots.add(root);

  const tabs = root.querySelectorAll(".tab-btn");
  const panels = root.querySelectorAll(".tab-panel");
  const graphHint = root.querySelector("[data-graph-hint]");

  function syncGraphHint(activeTab) {
    if (!graphHint) return;
    graphHint.classList.toggle("hidden", activeTab !== "graph");
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;

      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      const panel = root.querySelector("#tab-" + target);
      if (panel) panel.classList.add("active");

      syncGraphHint(target);
    });
  });

  // Initial state: the default active tab is Search (see scholar.html), so the
  // graph hint is hidden on load.
  const initial = root.querySelector(".tab-btn.active");
  if (initial) syncGraphHint(initial.dataset.tab);
}

function initScholarRoots() {
  document.querySelectorAll("[data-scholar-root]").forEach(initScholarTabs);
}

// The host replaces the pane before announcing the injected module.
document.addEventListener("workspace:module-injected", (event) => {
  if (event.detail?.module === "scholar") initScholarRoots();
});

// A module may finish loading after the host's injection event or DOM ready.
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initScholarRoots, { once: true });
} else {
  initScholarRoots();
}
