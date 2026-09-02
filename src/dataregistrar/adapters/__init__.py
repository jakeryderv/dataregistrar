"""Adapter protocol and discovery. Adapters decide what exists."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Protocol, runtime_checkable

from dataregistrar.model import Kind, Record

ENTRY_POINT_GROUP = "dataregistrar.adapters"


@runtime_checkable
class Adapter(Protocol):
    """One source. `search` and `get` return normalized records, never raw provider shapes."""

    id: str
    kinds: frozenset[Kind]

    def search(self, query: str) -> list[Record]: ...

    def get(self, source_id: str) -> Record: ...


class AdapterFactory(Protocol):
    def __call__(self, source_id: str, **config: Any) -> Adapter: ...


def discover_adapters() -> dict[str, AdapterFactory]:
    """Adapter factories registered under the entry-point group, keyed by name."""
    found: dict[str, AdapterFactory] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        found[ep.name] = ep.load()
    return found


__all__ = ["ENTRY_POINT_GROUP", "Adapter", "AdapterFactory", "discover_adapters"]
