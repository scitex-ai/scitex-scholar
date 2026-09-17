# Scholar project picker — browser evidence (2026-09-17)

Evidence for the leaf-migration slice's outstanding acceptance gate: "run a real
390px browser regression" / "return browser evidence". Produced by driving a real
Chrome against the branch's own Django server on the branch's own code, not by
unit tests and not against a mock.

## What was run

Server (branch head, standalone mode, headless):

```bash
cd /uvwork/wt-scholar-175
PYTHONPATH=src \
SCITEX_SCHOLAR_LIBRARY_ROOT=<EVIDENCE>/library \
SCITEX_SCHOLAR_PROJECTS_DIR=<EVIDENCE>/library \
/uvwork/venv-agent/bin/python -c "from scitex_scholar._django import _server; _server.run(port=31477, host='127.0.0.1', open_browser=False)"
```

The library root is a REAL storage layout, not a bare temp dir — it holds the
reserved directories a user's library actually grows:

```
library/MASTER/AECB5227/metadata.json   (deduplicated store; internal)
library/MASTER_quarantine/              (internal)
library/downloads/                      (PDF staging; internal)
library/Alpha/Local-LocalCorpus-2024 -> ../MASTER/AECB5227   (a project)
library/Beta/                           (a project)
```

Browser: Chrome for Testing 153.0.8010.47, headless, e.g.

```bash
chrome --headless --no-sandbox --disable-gpu --virtual-time-budget=8000 \
       --window-size=390,844 --screenshot=<EVIDENCE>/screenshots/mobile-390x844.png \
       "http://127.0.0.1:31477/"
```

## 1. Authorized project vs internal store (the blocker-3 defect, in a browser)

`GET /?project=<id>` renders `data-current` from `resolve_project`, i.e. only an
id the provider actually offers can become the current project:

| Request | Rendered `data-current` | Meaning |
| --- | --- | --- |
| `/?project=Alpha` | `Alpha` | real project → selected |
| `/?project=Beta` | `Beta` | real project → selected |
| `/?project=MASTER` | `` (empty) | **internal store → not selectable** |
| `/?project=downloads` | `` (empty) | **internal staging dir → not selectable** |

The listing endpoint against the same real root returns only the projects:

```
$ curl -s http://127.0.0.1:31477/api/projects
projects listed: ['Alpha', 'Beta']   current: None
```

## 2. One canonical picker, mounted, in the canonical header slot

Rendered DOM (`--dump-dom`, desktop 1440 and mobile 390 respectively):

- exactly ONE `data-stx-project-picker` element; the second textual match is the
  same element carrying the SDK's `data-stx-project-picker-mounted` marker, i.e.
  the shared scitex-ui JS mounted it;
- `data-provider-url="/api/projects"`, `data-navigate="?project={id}"`;
- the element sits in `stx-app-header__slot--project-selector`.

## 3. Rendered layout at 1440x900 and 390x844

Screenshots (kept in shared scratch, not committed — binary):
`<EVIDENCE>/screenshots/desktop-1440x900.png`, `.../mobile-390x844.png`.

- **1440x900** — picker visible in the header showing "Select project"; no
  horizontal overflow, no clipped or overlapping header content; tabs render
  `Search databases` / `Library` / `Citation Graph`.
- **390x844** — the picker renders as a full-width row below the app identity
  (the documented mobile wrap), no content extends past the right edge, the
  control is ~44-48 px tall (>= the 44px touch target), and all three tab labels
  fit on one row untruncated.

## 4. Honest notes and one nit

- The literal string `MASTER` DOES appear once in the rendered DOM: inside an HTML
  **source comment** of the Library filter block ("...over the same MASTER
  metadata the list shows"). It is not user-visible text, no visible label,
  option, or copy contains it, and the picker never offers it. Removable on
  request; recorded here rather than left for a reviewer to find by grep.
- Verification is against a seeded real storage root, not a user's live library,
  and the **hub-mounted** render (`/apps/scholar/v2/`) is still unverified here —
  no hub/docker runtime exists on this node.
- Environment: the Hermes browser tool could not start in this session
  ("Chromium browser is missing" despite Chrome being installed and launching),
  so Chrome was driven directly; that is why the evidence is screenshots + DOM
  dumps + the commands above rather than a browser-tool trace.
