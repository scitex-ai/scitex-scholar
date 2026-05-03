---
description: |
  [TOPIC] Authentication
  [DETAILS] OpenAthens / Shibboleth SSO authentication for institutional PDF access.
tags: [scitex-scholar-authentication, scitex-scholar]
---


# Authentication

Scholar uses **OpenAthens** (and Shibboleth-compatible) SSO to access paywalled PDFs through your institution's subscription. Cookies are cached so subsequent runs don't re-prompt.

## Quick check

```bash
# Status only — no browser launch
scitex scholar config            # Shows library + auth state
```

```python
from scitex_scholar.auth import ScholarAuthManager

auth = ScholarAuthManager()
auth.check_status(method="openathens")           # → bool
auth.check_status(method="openathens", verify_live=True)  # opens session check
```

## Login

```python
auth.authenticate(method="openathens", institution="University of Melbourne")
```

This launches a Chromium window. Sign in with your institutional credentials and complete MFA (e.g. Okta Verify push). The session cookies are persisted to:

```
~/.scitex/scholar/cache/auth/openathens.json
```

Subsequent pipeline runs reuse this file until cookies expire.

## Cookie file

Important entries written to `openathens.json`:
- `myAthens` session cookie
- Federated `_shibsession_*` (per-resource)
- `oamps` (OpenAthens MPS)

If a publisher fails authorization despite a "logged in" status, expire the cache and re-auth:

```bash
rm ~/.scitex/scholar/cache/auth/openathens.json
```

## Environment variables

For automated environments, source institution-specific env files (Unimelb example):

```bash
source ~/.dotfiles/.bash.d/secrets/000_ENV_UNIMELB.src
source ~/.dotfiles/.bash.d/secrets/001_ENV_SCITEX.src
```

Common variables:
- `SCITEX_SCHOLAR_OPENATHENS_USERNAME`
- `SCITEX_SCHOLAR_2CAPTCHA_API_KEY` (for CAPTCHA solver extension)

## MCP

```
scholar_authenticate(method="openathens", confirm=True)
scholar_check_auth_status(method="openathens", verify_live=True)
scholar_logout(method="openathens")
```

## MFA / CAPTCHA escalation

During pipeline runs the authenticator detects when human input is needed (Okta Verify push, hCaptcha) and either:
- Pauses and shows a visible browser tab (interactive mode)
- Sends a notification via `scitex-notification` (configured backend)

See [scitex-notification](../../scitex-notification/SKILL.md) for phone-call/SMS escalation when running unattended.
