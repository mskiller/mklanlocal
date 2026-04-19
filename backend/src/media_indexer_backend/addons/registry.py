from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from media_indexer_backend.addons.models import AddonPreset
    from media_indexer_backend.models.tables import Asset, Collection, User


@dataclass(slots=True)
class AddonPresetSeed:
    name: str
    description: str | None = None
    config_json: dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass(slots=True)
class GeneratedArtifact:
    filename: str
    content: bytes
    mime_type: str
    label: str
    asset_id: str | None = None
    width: int | None = None
    height: int | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AddonExecutionContext:
    session: Session
    current_user: User
    module_id: str
    module_settings: dict[str, Any]
    params_json: dict[str, Any]
    scope_type: str
    scope_json: dict[str, Any]
    assets: list[Asset]
    collection: Collection | None
    preset: AddonPreset | None
    recipe_version: int


PerAssetProcessor = Callable[[AddonExecutionContext, "Asset"], list[GeneratedArtifact]]
JobProcessor = Callable[[AddonExecutionContext], list[GeneratedArtifact]]


@dataclass(slots=True)
class AddonDefinition:
    module_id: str
    name: str
    description: str
    supports_asset: bool = True
    supports_batch: bool = True
    supports_collection: bool = False
    default_presets: list[AddonPresetSeed] = field(default_factory=list)
    per_asset_processor: PerAssetProcessor | None = None
    job_processor: JobProcessor | None = None


_ADDON_DEFINITIONS: dict[str, AddonDefinition] = {}


def register_addon_definition(definition: AddonDefinition) -> None:
    _ADDON_DEFINITIONS[definition.module_id] = definition


def get_addon_definition(module_id: str) -> AddonDefinition | None:
    return _ADDON_DEFINITIONS.get(module_id)
