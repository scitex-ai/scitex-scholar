# Scholar GUI stylesheets

`scholar.css` is the entry point and the only stylesheet the template links.
It contains no rules — it `@import`s the partials in `_partials/` in cascade
order.

## Layout

| File                      | Owns                                                |
|---------------------------|-----------------------------------------------------|
| `_partials/_base.css`     | Design tokens (`:root` variables), reset, base tags  |
| `_partials/_layout.css`   | App shell (header, sidebar, main), tab navigation    |
| `_partials/_sidebar.css`  | Sidebar sections, status indicators                  |
| `_partials/_cards.css`    | Tab content container, card chrome                   |
| `_partials/_forms.css`    | Inputs, selects, labels, buttons                     |
| `_partials/_graph.css`    | Citation graph canvas, nodes, edges, tooltip, panel  |
| `_partials/_papers.css`   | Related-papers list, score bars                      |
| `_partials/_search.css`   | Search tab result list                               |
| `_partials/_states.css`   | Loading, error, placeholder, `.hidden`               |

## Rules

- **Cascade order is load-bearing.** `_base.css` defines the tokens every
  other partial reads, and `_states.css` ends with `.hidden { display: none
  !important; }`. Keep the import order in `scholar.css` as-is unless you have
  checked what depends on it.
- **No inline `style=` attributes in templates** — a pre-commit hook blocks
  them. Add a class to the partial that owns the concern instead.
- **Dark theme by default.** Use the `--bg-*` / `--text-*` / `--accent` tokens
  rather than literal colours, so a theme change stays a one-file edit.
- Partials are capped at 512 lines each, like every other file in the repo.
  If one outgrows that, split it by concern rather than trimming rules.
