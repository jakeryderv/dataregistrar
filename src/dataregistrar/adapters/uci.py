"""UCI Machine Learning Repository adapter.

The UCI JSON API exposes name, abstract, tasks, DOI, and creators, but no license field.
The website shows a license per dataset, but this adapter never guesses from a page:
records import with rights unknown, and an overlay supplies the verified license.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import HttpUrl

from dataregistrar.download import download_all
from dataregistrar.model import AccessPlan, Kind, PlannedFile, Record, Status

BASE_URL = "https://archive.ics.uci.edu"


class UCIAdapter:
    id: str
    kinds: frozenset[Kind] = frozenset({Kind.DATASET})

    def __init__(
        self,
        source_id: str = "uci",
        *,
        client: httpx.Client | None = None,
        **config: Any,
    ) -> None:
        self.id = source_id
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=30)

    def _record_id(self, uci_id: int | str) -> str:
        return f"{self.id}:{uci_id}"

    def search(self, query: str) -> list[Record]:
        """Name-based search via the list endpoint. Returns shallow records, status `discovered`."""
        payload = self._get_json("/api/datasets/list", params={"search": query})
        hits: list[dict[str, Any]] = payload["data"]
        return [
            Record(
                id=self._record_id(hit["id"]),
                kind=Kind.DATASET,
                source=self.id,
                name=hit["name"],
                url=HttpUrl(f"{BASE_URL}/dataset/{hit['id']}"),
                publisher="UCI Machine Learning Repository",
                status=Status.DISCOVERED,
                source_metadata=hit,
            )
            for hit in hits
        ]

    def get(self, source_id: str) -> Record:
        """Full record from the detail endpoint. Status `imported`; rights stay unknown."""
        payload = self._get_json("/api/dataset", params={"id": source_id})
        d: dict[str, Any] = payload["data"]
        doi = d.get("dataset_doi")
        tasks: list[str] = d.get("tasks") or []
        return Record(
            id=self._record_id(d["uci_id"]),
            kind=Kind.DATASET,
            source=self.id,
            name=d["name"],
            url=d.get("repository_url"),
            description=d.get("abstract"),
            publisher="UCI Machine Learning Repository",
            cite_as=f"https://doi.org/{doi}" if doi else None,
            modality="tabular",
            tasks=[t.lower() for t in tasks],
            status=Status.IMPORTED,
            source_metadata=d,
        )

    def resolve(self, record: Record) -> AccessPlan:
        """One file: the `data_url` the API reports. Shallow records are fetched first."""
        if "data_url" not in record.source_metadata:
            record = self.get(record.id.partition(":")[2])
        url: str = record.source_metadata["data_url"]
        filename = Path(urlsplit(url).path).name or "data"
        return AccessPlan(
            record_id=record.id,
            kind=Kind.DATASET,
            files=[PlannedFile(url=HttpUrl(url), filename=filename)],
        )

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        return download_all(self._client, plan, destination)

    def _get_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        if body.get("status") != 200:
            raise httpx.HTTPError(f"UCI API returned status {body.get('status')} for {path}")
        return body
