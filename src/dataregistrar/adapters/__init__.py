"""Adapter protocol and discovery. Adapters decide what exists and how to get it."""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from dataregistrar.model import AccessPlan, Kind, Record

ENTRY_POINT_GROUP = "dataregistrar.adapters"


class AccessRequired(Exception):
    """The source will not hand over the bytes without credentials or approval."""


@runtime_checkable
class Adapter(Protocol):
    """One source. Returns normalized records and plans, never raw provider shapes."""

    id: str
    kinds: frozenset[Kind]

    def search(self, query: str) -> list[Record]: ...

    def get(self, source_id: str) -> Record: ...

    def resolve(self, record: Record) -> AccessPlan:
        """What retrieving this record would fetch. No network side effects beyond metadata."""
        ...

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        """Fetch the plan's files into `destination` and return their paths, in plan order."""
        ...


class AdapterFactory(Protocol):
    def __call__(self, source_id: str, **config: Any) -> Adapter: ...


def discover_adapters() -> dict[str, AdapterFactory]:
    """Adapter factories registered under the entry-point group, keyed by name."""
    found: dict[str, AdapterFactory] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        found[ep.name] = ep.load()
    return found


__all__ = ["ENTRY_POINT_GROUP", "AccessRequired", "Adapter", "AdapterFactory", "discover_adapters"]
