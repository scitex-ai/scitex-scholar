"""Package the leaf descriptor through the SDK's inert metadata producer."""

from __future__ import annotations

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from scitex_sdk.app.api_build import prepare_hatch_api_metadata


class CustomBuildHook(BuildHookInterface):
    """Keep the SDK-owned temporary metadata alive until the wheel is complete."""

    def initialize(self, version, build_data):
        if self.target_name == "wheel":
            self._api_metadata = prepare_hatch_api_metadata(self, build_data)

    def finalize(self, version, build_data, artifact_path):
        metadata = getattr(self, "_api_metadata", None)
        if metadata is not None:
            metadata.cleanup()
