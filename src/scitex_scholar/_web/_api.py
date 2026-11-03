"""Static documentation contract; importing it never resolves a Django handler."""

from __future__ import annotations

from scitex_sdk.app.api_plugin import (
    ApiField,
    ApiPlugin,
    ApiRoute,
    ApiSchema,
    Audit,
    AuthScope,
    RateLimit,
)

plugin = ApiPlugin(
    id="scitex-scholar",
    title="SciTeX Scholar search syntax help",
    api_version="1",
    routes=(
        ApiRoute(
            path="api/search/syntax-help",
            methods=("GET",),
            response=ApiSchema(
                name="ScholarSearchSyntaxHelp",
                fields=(
                    ApiField(name="status", enum=("success",)),
                    ApiField(name="syntax", type="object"),
                    ApiField(name="examples", type="array"),
                    ApiField(
                        name="available_sources",
                        type="array",
                        description="Documented source names, not a live availability check.",
                    ),
                    ApiField(
                        name="query_parameters",
                        type="object",
                        description="Parameters documented for search; this help operation takes no input.",
                    ),
                ),
            ),
            auth=AuthScope(public=True, project_scope="none"),
            rate=RateLimit(
                rate_class="standard",
                compute_cost="light",
                quota_note="Static documentation; enforcement is host policy, not a leaf quota counter.",
            ),
            audit=Audit(level="none"),
            handler="scitex_scholar._web._views:search_syntax_help",
            read_only=True,
        ),
    ),
)
