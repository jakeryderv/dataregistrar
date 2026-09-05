"""NOAA adapter: one publisher, many delivery mechanisms.

Discovery goes through NCEI's catalog. Retrieval goes through collections, each of which
knows one delivery mechanism. Catalog entries with no collection are metadata-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from dataregistrar.adapters import NoRetrievalPath
from dataregistrar.adapters.noaa import catalog
from dataregistrar.adapters.noaa.collections import Collection
from dataregistrar.adapters.noaa.collections.ghcn_daily import GHCNDaily
from dataregistrar.adapters.noaa.collections.storm_events import StormEvents
from dataregistrar.download import download_all
from dataregistrar.model import AccessPlan, Kind, Record

BASE_URL = "https://www.ncei.noaa.gov"
COLLECTIONS: tuple[Collection, ...] = (StormEvents(), GHCNDaily())
CATALOG_PREFIX = "ncei/"


class NOAAAdapter:
    id: str
    kinds: frozenset[Kind] = frozenset({Kind.DATASET, Kind.RELEASE_SERIES})

    def __init__(
        self,
        source_id: str = "noaa",
        *,
        client: httpx.Client | None = None,
        limit: int = 20,
        collections: tuple[Collection, ...] = COLLECTIONS,
        **config: Any,
    ) -> None:
        self.id = source_id
        self.limit = limit
        self.collections = {c.id: c for c in collections}
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=True)

    def search(self, query: str) -> list[Record]:
        """Collections come first, then NCEI catalog hits. A catalog hit whose id a collection
        claims is replaced by that collection, so one dataset never appears twice."""
        matched = [c for c in self.collections.values() if c.matches(query)]
        hits: list[Record] = []
        for d in catalog.search(self._client, query, self.limit):
            claimed = self.collections.get(f"{CATALOG_PREFIX}{d['id']}")
            if claimed is None:
                hits.append(catalog.to_record(self.id, d))
            elif claimed not in matched:
                matched.append(claimed)
        return [c.summary(self.id) for c in matched] + hits

    def get(self, source_id: str) -> Record:
        if source_id in self.collections:
            return self.collections[source_id].detail(self._client, self.id)
        if source_id.startswith(CATALOG_PREFIX):
            wanted = source_id.removeprefix(CATALOG_PREFIX)
            for d in catalog.search(self._client, None, 500):
                if d.get("id") == wanted:
                    return catalog.to_record(self.id, d)
        raise LookupError(f"{self.id}:{source_id} is neither a collection nor an NCEI catalog id")

    def resolve(self, record: Record, selector: str | None = None) -> AccessPlan:
        native = record.id.partition(":")[2]
        collection = self.collections.get(native)
        if collection is None:
            raise NoRetrievalPath(record.id, str(record.url) if record.url else None)
        return collection.resolve(self._client, self.id, record, selector)

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        return download_all(self._client, plan, destination)
