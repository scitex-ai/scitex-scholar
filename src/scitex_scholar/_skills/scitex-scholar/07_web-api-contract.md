---
description: Discover Scholar's static syntax-help Web API descriptor without activating a host route.
tags: [scitex-scholar, web-api, metadata]
---

# Static syntax-help Web API

The `scitex.apis` provider `scitex-scholar` currently describes only
`GET api/search/syntax-help`. It returns the existing static help document;
`available_sources` is documentation, not runtime availability. Search, library
and graph operations are outside this canonical descriptor.

Use the SDK's `discover_api_plugins()` and
`read_inert_descriptor("scitex-scholar")` for metadata discovery. The descriptor
is `scitex_scholar._web._api:plugin`; its handler lazily delegates to the native
view. Reading metadata does not start Django, run a search, select a project or
activate an endpoint. Host admission and mounting remain explicit.

The operation takes no search parameters and needs no project or OAuth scope.
Django's existing non-GET response remains a non-JSON 405 with `Allow: GET`.
Serving still requires the optional Django stack and configured host; source
registration alone does not prove installed metadata or live availability.

```python
from scitex_sdk.app.api_plugin import discover_api_plugins
from scitex_sdk.app.api_mount import read_inert_descriptor

refs = discover_api_plugins()
plugin = read_inert_descriptor("scitex-scholar")
```

Runtime descriptors require SDK >=0.3.17; source builds require SDK >=0.3.20
for its shared metadata producer. Until that build dependency is published and
qualified, this is a draft source follow-up. See `docs/static-api-provider.md`
for the source contract and packaging checks.
