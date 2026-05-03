---
description: |
  [TOPIC] Extraction Lessons
  [DETAILS] failure-outcome metadata, artifact-count truthfulness, single-worker per publisher, Xvfb timeout handling, OpenAthens redirect semantics. These are scholar-implementation lore, not general arch rul...
tags: [scitex-scholar-extraction-lessons, scitex-scholar, lessons]
canonical-location: scitex-scholar/src/scitex_scholar/_skills/scitex-scholar/30_extraction-lessons.md
---


# scitex-scholar — Extraction Lessons

These are case-study lessons from extracting `scitex-scholar` (and `scitex-browser`) out of the scitex monolith in April 2026. They're scholar-specific lore: useful for anyone touching the download/enrichment pipeline or the OpenAthens auth flow, but **not** general SciTeX arch rules.

For general arch rules, see [scitex-python `general/01_ecosystem_03_modules-and-standalone-packages.md`](../../../../scitex-python/src/scitex/_skills/general/01_ecosystem_03_modules-and-standalone-packages.md).

## 1. Record failure outcomes in metadata, not just logs

Long-running pipelines (download, enrichment) should populate metadata fields like `access.pdf_download_{attempted_at, status, error}` on **every** terminal branch — success, no-URLs, auth-failed, download-failed. A project symlink to a paper without a PDF must be self-describing; otherwise consumers can't tell "paywalled" from "not yet attempted".

## 2. "Pipeline Successful: N" ≠ "N papers got PDFs"

Report the actual artifact count, not the workflow-completed count. `Successful: 10 / Failed: 0` with zero PDFs downloaded is a false positive that masks the real problem. The headline metric must be the artifact count.

## 3. One worker against a single publisher

Publisher bot detection (Cloudflare, OpenAthens SSO) triggers on concurrent requests to the same host. Four parallel workers hitting `academic.oup.com` at once reliably trips Cloudflare; one worker at a time succeeds. A per-host rate limiter is the right abstraction; until that exists, default `--num-workers 1` for paywalled publishers.

## 4. Xvfb auto-start must handle timeout, not only nonzero exit

`xdpyinfo` can hang against a missing display rather than returning non-zero. Verifier code like

```python
if subprocess.run([...], timeout=5).returncode == 0: ok
else: start_xvfb()
```

misses the timeout path entirely (the `except TimeoutExpired` branch returns `False` without starting anything). Always take the start-Xvfb branch on any failure mode, with a recursion guard.

## 5. `wait_redirects` success needs a semantic check, not just "settled"

OpenAthens SSO redirect chains can take 25–35 s — longer than most "wait for navigation to settle" timeouts. If the timeout fires but the page URL has left the origin resolver (`sfxlcl`, `exlibrisgroup`), that IS success. Strict `success = not timed_out AND ...` discards valid resolutions and forces the caller to fall back to the original OpenURL, producing "Found 0 PDF URLs" on pages that have no PDFs.
