---
description: |
  [TOPIC] Env Vars
  [DETAILS] see general/10_arch-environment-variables.md.
tags: [scitex-scholar-env-vars, scitex-scholar]
---


# scitex-scholar — Environment Variables

Only the `SCITEX_SCHOLAR_*` family is module-owned; ecosystem-shared vars
(`SCITEX_CLOUD_*`, `SCITEX_NOTIFICATION_*`, etc.) are documented by their
owning packages and only consumed read-only here.

## Project / paths

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_PROJECT` | Default scholar project name. | `default` | string |

## Email / SSO / SMTP

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_EMAIL_FROM` | "From" address for outbound email. | `—` | string |
| `SCITEX_SCHOLAR_FROM_EMAIL_ADDRESS` | Legacy alias. | inherits | string |
| `SCITEX_SCHOLAR_FROM_EMAIL_PASSWORD` | SMTP password. | `—` | string |
| `SCITEX_SCHOLAR_FROM_EMAIL_SMTP_SERVER` | SMTP host. | `—` | string |
| `SCITEX_SCHOLAR_FROM_EMAIL_SMTP_PORT` | SMTP port. | `587` | int |
| `SCITEX_SCHOLAR_NOTIFICATION_EMAIL` | Destination for scholar notifications. | `—` | string |
| `SCITEX_SCHOLAR_ALERT_BACKENDS` | Comma-separated list of alert backends. | `email` | string (CSV) |
| `SCITEX_SCHOLAR_SSO_EMAIL` / `_USERNAME` / `_PASSWORD` | Generic SSO credentials. | `—` | string |
| `SCITEX_SCHOLAR_SHIBBOLETH_EMAIL` | Shibboleth login email. | `—` | string |

## Paywall / OpenAthens

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_ENABLE_PAYWALL_ACCESS` | Opt-in: allow authenticated paywall traversal. | `false` | bool |
| `SCITEX_SCHOLAR_TRACK_PAYWALL_ATTEMPTS` | Log every paywall attempt for audit. | `false` | bool |
| `SCITEX_SCHOLAR_OPENATHENS_ENABLED` | Opt-in: OpenAthens backend. | `false` | bool |
| `SCITEX_SCHOLAR_OPENATHENS_EMAIL` | OpenAthens email. | `—` | string |
| `SCITEX_SCHOLAR_OPENATHENS_USERNAME` | OpenAthens username. | `—` | string |
| `SCITEX_SCHOLAR_OPENATHENS_IDP_URL` | IdP endpoint URL. | `—` | URL |
| `SCITEX_SCHOLAR_OPENATHENS_ORG_ID` | Organization ID. | `—` | string |
| `SCITEX_SCHOLAR_OPENURL_RESOLVER_URL` | Institutional OpenURL resolver. | `—` | URL |
| `SCITEX_SCHOLAR_EZPROXY_EMAIL` | EZproxy email. | `—` | string |

## Anti-bot / CAPTCHA

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_2CAPTCHA_API_KEY` | 2Captcha API key. | `—` | string |
| `SCITEX_SCHOLAR_ZENROWS_API_KEY` | ZenRows API key. | `—` | string |
| `SCITEX_SCHOLAR_ZENROWS_PROXY_COUNTRY` | ZenRows geo override. | unset | string (country code) |

## Backend APIs

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_CROSSREF_API_KEY` | CrossRef API key (polite pool). | `—` | string |
| `SCITEX_SCHOLAR_CROSSREF_API_URL` | CrossRef endpoint override. | api.crossref.org | URL |
| `SCITEX_SCHOLAR_CROSSREF_EMAIL` | Mailto for CrossRef polite pool. | `—` | string |
| `SCITEX_SCHOLAR_CROSSREF_DB` | Local crossref-local DB path. | `~/.scitex/scholar/crossref/works.db` | path |
| `SCITEX_SCHOLAR_OPENALEX_API_URL` | OpenAlex endpoint override. | api.openalex.org | URL |
| `SCITEX_SCHOLAR_PUBMED_API_KEY` | PubMed API key. | `—` | string |
| `SCITEX_SCHOLAR_PUBMED_EMAIL` | PubMed mailto. | `—` | string |
| `SCITEX_SCHOLAR_SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar API key. | `—` | string |
| `SCITEX_SCHOLAR_UNPAYWALL_EMAIL` | Unpaywall mailto. | `—` | string |

## PDF / download

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_AUTO_DOWNLOAD` | Auto-download PDFs after enrichment. | `false` | bool |
| `SCITEX_SCHOLAR_AUTO_ENRICH` | Auto-enrich on BibTeX import. | `true` | bool |
| `SCITEX_SCHOLAR_PREFER_OPEN_ACCESS` | Prefer OA versions over paywalled. | `true` | bool |
| `SCITEX_SCHOLAR_PDF_USE_PARALLEL` | Use parallel PDF downloads. | `true` | bool |
| `SCITEX_SCHOLAR_PDF_MAX_PARALLEL` | Max concurrent PDF downloads. | `4` | int |
| `SCITEX_SCHOLAR_MAX_RETRIES` | Retry budget per operation. | `3` | int |

## Cache

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_USE_CACHE_DOWNLOAD` | Cache PDF downloads. | `true` | bool |
| `SCITEX_SCHOLAR_USE_CACHE_ENGINE` | Cache search-engine responses. | `true` | bool |
| `SCITEX_SCHOLAR_USE_CACHE_URL` | Cache URL resolutions. | `true` | bool |

## Misc

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `SCITEX_SCHOLAR_CAPTURE_SCREENSHOTS` | Capture debug screenshots during browser sessions. | `false` | bool |
| `SCITEX_SCHOLAR_CHROME_PROFILE_NAME` | Named Chrome profile for authenticated sessions. | `scholar` | string |
| `SCITEX_SCHOLAR_DEBUG_MODE` | Verbose tracing. | `false` | bool |

## Feature flags

- **opt-out:** `SCITEX_SCHOLAR_AUTO_ENRICH=false`,
  `SCITEX_SCHOLAR_PREFER_OPEN_ACCESS=false`,
  `SCITEX_SCHOLAR_PDF_USE_PARALLEL=false`,
  `SCITEX_SCHOLAR_USE_CACHE_*=false`.
- **opt-in (external / security-sensitive):**
  `SCITEX_SCHOLAR_OPENATHENS_ENABLED=true`,
  `SCITEX_SCHOLAR_ENABLE_PAYWALL_ACCESS=true`,
  `SCITEX_SCHOLAR_TRACK_PAYWALL_ATTEMPTS=true`,
  `SCITEX_SCHOLAR_AUTO_DOWNLOAD=true`,
  `SCITEX_SCHOLAR_CAPTURE_SCREENSHOTS=true`,
  `SCITEX_SCHOLAR_DEBUG_MODE=true`.

## Cross-package (read-only)

scitex-scholar also reads a broad set of ecosystem vars (`SCITEX_CLOUD_*`,
`SCITEX_NOTIFICATION_*`, `SCITEX_AUDIO_*`, `SCITEX_OROCHI_*`,
`SCITEX_WRITER_*`, `SCITEX_DEV_*`, `SCITEX_TUNNEL_*`, `SCITEX_UI_*`). These
are documented by their owning packages — set them there, not here.

## Audit

```bash
grep -rhoE 'SCITEX_[A-Z0-9_]+' $HOME/proj/scitex-scholar/src/ | sort -u
```
