"""Load overlays from each layer and merge them onto records. Later layers win."""

from __future__ import annotations

from typing import Any

from dataregistrar._yaml import load_yaml
from dataregistrar.model import Overlay, Record
from dataregistrar.registry.layers import Layer


class OverlayIndex:
    """Overlays keyed by every distribution id they cover, and by canonical id."""

    def __init__(self) -> None:
        self._by_distribution: dict[str, Overlay] = {}
        self._by_canonical: dict[str, Overlay] = {}

    def add(self, overlay: Overlay) -> None:
        self._by_canonical[overlay.canonical] = overlay
        for dist in overlay.distributions:
            self._by_distribution[dist.id] = overlay

    def for_record(self, record_id: str) -> Overlay | None:
        return self._by_distribution.get(record_id)

    def for_canonical(self, canonical: str) -> Overlay | None:
        return self._by_canonical.get(canonical)

    def __len__(self) -> int:
        return len(self._by_canonical)


def load_overlays(layers: list[Layer]) -> OverlayIndex:
    index = OverlayIndex()
    for layer in layers:
        if not layer.overlays_dir.is_dir():
            continue
        for path in sorted(layer.overlays_dir.glob("*.yaml")):
            raw: Any = load_yaml(path)
            overlay = Overlay.model_validate({**raw, "layer": layer.name})
            index.add(overlay)
    return index


def apply_overlay(record: Record, overlay: Overlay) -> Record:
    """Overlay fields win. Fields the overlay leaves None keep the record's value."""
    updates: dict[str, Any] = {"canonical": overlay.canonical}
    for field in ("kind", "name", "publisher", "cite_as", "license", "rights", "status"):
        value = getattr(overlay, field)
        if value is not None:
            updates[field] = value
    return record.model_copy(update=updates)
