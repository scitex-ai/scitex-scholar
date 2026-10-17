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
 *
 * Mobile swipe (operator request 2026-10-16, figrecipe parity): on phone
 * layouts the tabs also switch by horizontal swipe, following the SDK Panes
 * swipe contract (scitex_sdk/ui/ts/app/panes/_Panes.ts) that figrecipe's
 * phone panes inherit — 60px minimum travel, 1.5x horizontal dominance,
 * gestures starting inside interactive content (graph svg/canvas, form
 * fields, horizontal scrollers) belong to that content and never switch
 * tabs (operator mobile ruling 7724-7725). Gated on Scholar's own 768px
 * mobile breakpoint (its stacked single-column layout), so desktop
 * horizontal gestures (table scroll, graph pan) are never affected.
 */
const initializedRoots = new WeakSet();

// Minimum horizontal travel (px) for a touch to count as a tab-switch swipe.
const SWIPE_MIN_PX = 60;
// Horizontal travel must dominate vertical travel by this ratio, so vertical
// page scrolls never flip tabs.
const SWIPE_AXIS_RATIO = 1.5;
// Scholar's stacked mobile layout breakpoint (see _layout.css).
const PHONE_QUERY = "(max-width: 768px)";
// Gestures starting inside these belong to the content, not tab switching.
const NO_SWIPE_SELECTOR =
  "input, textarea, select, [contenteditable=''], [contenteditable='true'], " +
  "canvas, svg, table, iframe, embed, object, " +
  "[role='img'], [role='application'], [data-status-strip]";

function startsInsideOwnGesture(target, root) {
  for (let el = target; el && el !== root; el = el.parentElement) {
    if (el.matches && el.matches(NO_SWIPE_SELECTOR)) return true;
    if (el.scrollWidth > el.clientWidth + 1) {
      const overflow = getComputedStyle(el).overflowX;
      if (overflow === "auto" || overflow === "scroll") return true;
    }
  }
  return false;
}

function isPhoneLayout() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(PHONE_QUERY).matches
  );
}

function initScholarTabs(root) {
  if (initializedRoots.has(root)) return;
  initializedRoots.add(root);

  const tabs = Array.from(root.querySelectorAll(".tab-btn"));
  const panels = root.querySelectorAll(".tab-panel");
  const graphHint = root.querySelector("[data-graph-hint]");

  function syncGraphHint(activeTab) {
    if (!graphHint) return;
    graphHint.classList.toggle("hidden", activeTab !== "graph");
    // Operator 2026-10-17 (photo tour): the 240px left sidebar holds only
    // graph hints, so off-graph it renders as a mystery empty column.
    // Collapse it unless the Graph tab is active.
    root.classList.toggle("scholar-graph-active", activeTab === "graph");
  }

  function activateTab(tab) {
    const target = tab.dataset.tab;

    tabs.forEach((t) => t.classList.remove("active"));
    panels.forEach((p) => p.classList.remove("active"));

    tab.classList.add("active");
    const panel = root.querySelector("#tab-" + target);
    if (panel) panel.classList.add("active");

    syncGraphHint(target);
  }

  function stepTab(delta) {
    const index = tabs.findIndex((t) => t.classList.contains("active"));
    const next = tabs[index + delta];
    if (next) activateTab(next);
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab));
  });

  // Horizontal swipe-to-switch-tab, phone layouts only.
  let touchStart = null;
  root.addEventListener(
    "touchstart",
    (event) => {
      touchStart = null;
      if (!isPhoneLayout() || event.touches.length !== 1) return;
      if (startsInsideOwnGesture(event.target, root)) return;
      touchStart = {
        x: event.touches[0].clientX,
        y: event.touches[0].clientY,
      };
    },
    { passive: true },
  );
  root.addEventListener(
    "touchend",
    (event) => {
      const start = touchStart;
      touchStart = null;
      const touch = event.changedTouches[0];
      if (!start || !touch) return;
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      if (
        Math.abs(dx) < SWIPE_MIN_PX ||
        Math.abs(dx) < Math.abs(dy) * SWIPE_AXIS_RATIO
      ) {
        return;
      }
      stepTab(dx < 0 ? 1 : -1);
    },
    { passive: true },
  );

  // Status strip (right edge): collapse toggle. The strip minimizes to a
  // rail per the operator layout rule; the labels travel as data attributes
  // so the toggle never hardcodes a language.
  const strip = root.querySelector("[data-status-strip]");
  const stripToggle = strip
    ? strip.querySelector("[data-status-strip-toggle]")
    : null;
  if (strip && stripToggle) {
    stripToggle.addEventListener("click", () => {
      const collapsed = strip.classList.toggle("status-strip--collapsed");
      stripToggle.setAttribute("aria-expanded", String(!collapsed));
      stripToggle.setAttribute(
        "aria-label",
        collapsed
          ? stripToggle.dataset.labelExpand
          : stripToggle.dataset.labelCollapse,
      );
    });
  }

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
