"""Collections: one delivery mechanism each. Internal to the NOAA adapter."""

from __future__ import annotations

from typing import Protocol

import httpx

from dataregistrar.model import AccessPlan, Record


class Collection(Protocol):
    id: str
    """Service-qualified id, e.g. `ncei/storm-events`. Record id is `<source>:<this>`."""

    def matches(self, query: str) -> bool: ...

    def summary(self, source_id: str) -> Record:
        """Cheap record with no network call. Used in search results."""
        ...

    def detail(self, client: httpx.Client, source_id: str) -> Record:
        """Full record, releases listed."""
        ...

    def resolve(
        self, client: httpx.Client, source_id: str, record: Record, selector: str | None
    ) -> AccessPlan: ...
