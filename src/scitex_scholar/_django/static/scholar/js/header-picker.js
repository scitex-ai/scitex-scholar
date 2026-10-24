/* Scholar leaf header picker placement (storage-shaped).
 *
 * The SDK AppHeader primitive owns the header row and creates the canonical
 * `.stx-app-header__slot--project-selector` slot client-side on
 * DOMContentLoaded. The picker is server-rendered by the
 * `{% scitex_project_picker %}` tag (authed user + host provider only).
 * This module moves that element into the slot after both auto-mounts
 * have run. Deferred module: executes in document order after the mount
 * modules, so its DOMContentLoaded listener runs AFTER theirs and both
 * the header (and its slot) and the mounted picker exist when it fires.
 * Moving a mounted picker node preserves its component state (listeners
 * live on the element, not its position).
 *
 * Reads the header through window.stxAppHeader (set by the prebuilt
 * auto-mount module) — no bundler-relative imports that rot on move.
 *
 * Fail-soft: no picker (anon/standalone) or no mounted header means
 * nothing happens — the page keeps whatever the server rendered.
 */
function place() {
  const picker = document.querySelector("[data-stx-project-picker]");
  if (!picker) return;
  const api = window.stxAppHeader;
  const header = api && typeof api.get === "function" ? api.get() : null;
  if (header && header.projectSlot) {
    header.projectSlot.appendChild(picker);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", place);
} else {
  place();
}
