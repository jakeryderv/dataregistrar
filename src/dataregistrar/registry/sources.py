"""Load `sources.yaml` from each layer. Later layers override by source id."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataregistrar._yaml import load_yaml
from dataregistrar.model import Kind
from dataregistrar.registry.layers import Layer


class SourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    adapter: str
    kinds: list[Kind] = Field(default_factory=list[Kind])
    enabled: bool = True
    cache_ttl: float = 3600
    """Seconds a search or get response stays fresh. 0 disables caching for this source."""
    config: dict[str, Any] = Field(default_factory=dict)


class SourcesFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sources: list[SourceConfig] = Field(default_factory=list[SourceConfig])


def load_sources(layers: list[Layer]) -> dict[str, SourceConfig]:
    merged: dict[str, SourceConfig] = {}
    for layer in layers:
        if not layer.sources_file.is_file():
            continue
        raw: Any = load_yaml(layer.sources_file)
        for source in SourcesFile.model_validate(raw or {}).sources:
            merged[source.id] = source
    return {sid: s for sid, s in merged.items() if s.enabled}
