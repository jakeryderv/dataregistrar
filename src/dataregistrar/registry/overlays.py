"""Load overlays from each layer and merge them onto records. Later layers win."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from dataregistrar._yaml import load_yaml
from dataregistrar.model import Overlay, Record, Release, Status
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

    def __iter__(self) -> Iterator[Overlay]:
        return iter(self._by_canonical.values())


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
    for field in ("kind", "name", "publisher", "cite_as", "license", "rights"):
        value = getattr(overlay, field)
        if value is not None:
            updates[field] = value
    dist = next((d for d in overlay.distributions if d.id == record.id), None)
    checked = dist is None or dist.role == "official" or bool(dist.checksums)
    if overlay.status is not None and checked:
        updates["status"] = overlay.status
    if record.series is not None:
        releases, reissued = _link_reissues(record.series.releases, overlay, record.id)
        updates["series"] = record.series.model_copy(update={"releases": releases})
        if reissued and updates.get("status") == Status.VERIFIED:
            updates["status"] = Status.STALE
    return record.model_copy(update=updates)


def _link_reissues(
    releases: list[Release], overlay: Overlay, record_id: str
) -> tuple[list[Release], bool]:
    """Mark releases whose period an overlay recorded under a different filename.

    Planned filenames are `<period>/<name>`, so a recorded key with the same period prefix
    but a different name is an earlier issue the upstream has since replaced.
    """
    dist = next((d for d in overlay.distributions if d.id == record_id), None)
    if dist is None or not dist.checksums:
        return releases, False
    recorded = set(dist.checksums)
    linked: list[Release] = []
    reissued = False
    for release in releases:
        if release.filename not in recorded:
            earlier = next((k for k in recorded if k.startswith(release.id + "/")), None)
            if earlier is not None:
                release = release.model_copy(update={"supersedes": earlier})
                reissued = True
        linked.append(release)
    return linked, reissued
