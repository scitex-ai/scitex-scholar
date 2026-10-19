/**
 * Scholar GUI - Producer for the SDK content-tabs primitive.
 *
 * The tab BAR is styled by scitex_sdk/ui/css/app/content-tabs.css (the SSoT
 * sheet, linked in the workspace_assets head). This module is the producer
 * that contract names: it owns the tablist's live state — aria-selected +
 * roving tabindex + ArrowLeft/ArrowRight — and the CSS reads aria-selected
 * only, so the selected look can never fork from the shared primitive.
 * Scholar keeps just its panel show/hide (.tab-panel/.active in _layout.css);
 * panels are not part of the shared primitive.
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

  // Producer state for the SDK content-tabs primitive: the shared sheet reads
  // aria-selected only, so selection lives in attributes, never in
  // leaf-owned classes.
  const tabs = Array.from(root.querySelectorAll(".stx-content-tabs__tab"));
  const panels = root.querySelectorAll(".tab-panel");
  const graphHint = root.querySelector("[data-graph-hint]");

  function tabKey(tab) {
    return (tab.getAttribute("aria-controls") || "").replace(/^tab-/, "");
  }

  function syncGraphHint(key) {
    if (!graphHint) return;
    graphHint.classList.toggle("hidden", key !== "graph");
  }

  function activateTab(tab, focus) {
    tabs.forEach((t) => {
      const selected = t === tab;
      t.setAttribute("aria-selected", String(selected));
      t.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((p) => p.classList.remove("active"));

    const controls = tab.getAttribute("aria-controls");
    const panel = controls
      ? root.querySelector("#" + CSS.escape(controls))
      : null;
    if (panel) panel.classList.add("active");

    if (focus) tab.focus();
    syncGraphHint(tabKey(tab));
  }

  function stepTab(delta, focus) {
    const index = tabs.findIndex(
      (t) => t.getAttribute("aria-selected") === "true",
    );
    const next = tabs[index + delta];
    if (next) activateTab(next, focus);
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab, false));
    // Roving tabindex: ArrowLeft/ArrowRight move selection AND focus, per
    // the content-tabs producer contract (arrows only — no Home/End).
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") {
        event.preventDefault();
        stepTab(1, true);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        stepTab(-1, true);
      }
    });
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

  // Initial state: the default selected tab is Search (see
  // workspace_content.html), so the graph hint is hidden on load.
  const initial = root.querySelector(
    '.stx-content-tabs__tab[aria-selected="true"]',
  );
  if (initial) syncGraphHint(tabKey(initial));
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
