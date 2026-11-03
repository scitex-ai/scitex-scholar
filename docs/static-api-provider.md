# Static syntax-help API descriptor

Scholar declares one canonical `scitex.apis` provider, `scitex-scholar`, targeting
`scitex_scholar._web._api:plugin`. Its single operation describes the existing
relative `GET api/search/syntax-help` view. Search, library and citation-graph
operations are outside this descriptor.

The response has five required keys: `status`, `syntax`, `examples`,
`available_sources`, and `query_parameters`. The last two contain documentation,
not a live engine-health report or inputs accepted by this help operation.
The descriptor declares no request body, project scope, OAuth scopes, pagination,
leaf quota counter or request-audit behavior. Its standard/light classification
is metadata for host policy, not evidence that a rate limiter ran.

The small `_web._views` handler imports and delegates to the existing Django view
only when invoked. It preserves the native JSON GET response and non-JSON 405
responses with `Allow: GET`, including HEAD refusal. The large native view module
has repeated optional-import exception bindings that the bounded static reader
cannot prove; the lazy wrapper provides an explicit owned handler binding without
copying the document or changing its implementation.

Importing the descriptor, discovering its entry point, or reading its inert
metadata does not import Django or search engines. Serving the handler requires
the optional Django stack from `scitex-scholar[all]` and a configured Django host.
Native hosted access can also be restricted by that host's middleware. The
public/no-project declaration describes this static leaf operation; it does not
enable anonymous access on any deployment.

```python
from scitex_sdk.app.api_plugin import discover_api_plugins
from scitex_sdk.app.api_mount import read_inert_descriptor

refs = [ref for ref in discover_api_plugins() if ref.name == "scitex-scholar"]
plugin = read_inert_descriptor("scitex-scholar")
fragment = plugin.openapi_fragment() if plugin is not None else None
```

These are local metadata reads. Missing inert metadata is unknown, not permission
to import a provider as a fallback. A host must separately admit and mount a
provider; the descriptor supplies no deployment base URL and registration does
not activate a route.

The runtime descriptor uses the published SDK 0.3.17 constructor contract. Building
requires SDK 0.3.20 or newer for its shared inert metadata producer and
Hatchling >=1.27, qualified by the producer on Python 3.13. The normal
Hatch hook calls `prepare_hatch_api_metadata`; no descriptor JSON is maintained
in Scholar. Until that producer version is published and normal builds qualify,
this source change is a draft dependency follow-up, not a release-ready install.

The source declaration and HTTP behavior are covered by
`tests/scitex_scholar/_web/`. Build qualification must also verify the shared
SDK producer's `scitex_api.json` in wheel dist-info and its presence in a wheel
rebuilt from the sdist. A source-only declaration is not installed metadata.
