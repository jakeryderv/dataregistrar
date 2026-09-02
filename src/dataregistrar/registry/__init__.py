"""The registry: which sources are in play, and which overlays annotate them."""

from __future__ import annotations

from pathlib import Path

from dataregistrar.adapters import Adapter, AdapterFactory, discover_adapters
from dataregistrar.model import Record
from dataregistrar.registry.layers import Layer, default_layers
from dataregistrar.registry.overlays import OverlayIndex, apply_overlay, load_overlays
from dataregistrar.registry.sources import SourceConfig, load_sources


class Registry:
    def __init__(
        self,
        layers: list[Layer],
        *,
        factories: dict[str, AdapterFactory] | None = None,
    ) -> None:
        self.layers = layers
        self.factories = factories if factories is not None else discover_adapters()
        self.source_configs: dict[str, SourceConfig] = load_sources(layers)
        self.overlays: OverlayIndex = load_overlays(layers)
        self._adapters: dict[str, Adapter] = {}

    @classmethod
    def default(cls, cwd: Path | None = None) -> Registry:
        return cls(default_layers(cwd))

    @property
    def source_ids(self) -> list[str]:
        return list(self.source_configs)

    def adapter(self, source_id: str) -> Adapter:
        if source_id not in self._adapters:
            config = self.source_configs[source_id]
            try:
                factory = self.factories[config.adapter]
            except KeyError:
                raise LookupError(
                    f"source {source_id!r} needs adapter {config.adapter!r}, "
                    f"which is not installed; known: {sorted(self.factories)}"
                ) from None
            self._adapters[source_id] = factory(source_id, **config.config)
        return self._adapters[source_id]

    def annotate(self, record: Record) -> Record:
        """Merge the overlay for this record, if any. Overlay fields win."""
        overlay = self.overlays.for_record(record.id)
        return apply_overlay(record, overlay) if overlay else record


__all__ = ["Layer", "Registry", "SourceConfig", "default_layers"]
