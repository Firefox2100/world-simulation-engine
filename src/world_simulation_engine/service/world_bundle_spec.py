"""Persistent identifier for the world export/import bundle format (written into a bundle's
``manifest.json`` as ``spec``/``spec_version``), the same idea as a SillyTavern card's
``spec``/``spec_version`` fields: ``spec`` names the bundle format itself, ``spec_version`` is a
bare "MAJOR.MINOR" string bumped whenever the bundle's data shape changes, so any reader (this
codebase after a future data model change, or an external tool) can tell what shape of bundle it
is looking at and handle older bundles accordingly. Patch-level granularity is not tracked - this
is a data model, not expected to change often enough to need it.

Every writer/reader of a world bundle (``WorldExportService``/``WorldImportService``, the
evaluation test fixtures, and the standalone scripts under ``scripts/``) must go through this
module rather than hardcoding the spec/version, so there is exactly one place to bump on a future
data model change.
"""

WORLD_BUNDLE_SPEC = "wse_world"
WORLD_BUNDLE_SPEC_VERSION = "1.0"


def is_supported_world_bundle_manifest(manifest: object) -> bool:
    return (
        isinstance(manifest, dict)
        and manifest.get("spec") == WORLD_BUNDLE_SPEC
        and manifest.get("spec_version") == WORLD_BUNDLE_SPEC_VERSION
    )
