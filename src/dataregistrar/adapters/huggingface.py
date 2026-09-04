"""Hugging Face Hub adapter, over the Hub's HTTP API. No SDK dependency.

The Hub exposes a license tag per dataset. It is a self-declared tag, so records
import with rights derived from it at `imported` confidence, never `verified`.
Gated datasets import as `restricted` and are not downloaded without a token.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import HttpUrl

from dataregistrar.adapters import AccessRequired
from dataregistrar.download import download_all
from dataregistrar.model import Access, AccessPlan, Kind, License, PlannedFile, Record, Status
from dataregistrar.policy import derive_rights

BASE_URL = "https://huggingface.co"
TOKEN_ENV = "HF_TOKEN"

# Hub license tag → SPDX id. Tags with no clean SPDX equivalent are left out on purpose,
# so they import as spdx=None with the raw tag preserved in source_metadata.
LICENSE_TAGS: dict[str, str] = {
    "cc0-1.0": "CC0-1.0",
    "pddl": "PDDL-1.0",
    "cc-by-3.0": "CC-BY-3.0",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-sa-3.0": "CC-BY-SA-3.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc-by-nd-4.0": "CC-BY-ND-4.0",
    "cc-by-nc-nd-4.0": "CC-BY-NC-ND-4.0",
    "odc-by": "ODC-By-1.0",
    "odbl": "ODbL-1.0",
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "gpl-3.0": "GPL-3.0-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
}

DATA_SUFFIXES = {".csv", ".tsv", ".parquet", ".json", ".jsonl", ".txt", ".arrow"}


def _tag_values(tags: list[str], prefix: str) -> list[str]:
    return [t.removeprefix(prefix) for t in tags if t.startswith(prefix)]


class HuggingFaceAdapter:
    id: str
    kinds: frozenset[Kind] = frozenset({Kind.DATASET})

    def __init__(
        self,
        source_id: str = "hf",
        *,
        client: httpx.Client | None = None,
        token: str | None = None,
        limit: int = 20,
        **config: Any,
    ) -> None:
        self.id = source_id
        self.limit = limit
        self._token = token or os.environ.get(TOKEN_ENV)
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        self._client = client or httpx.Client(base_url=BASE_URL, headers=headers, timeout=30)

    def search(self, query: str) -> list[Record]:
        params = {"search": query, "limit": self.limit, "sort": "downloads", "direction": -1}
        hits: list[dict[str, Any]] = self._get_json("/api/datasets", params=params)
        return [self.to_record(hit) for hit in hits]

    def get(self, source_id: str) -> Record:
        detail: dict[str, Any] = self._get_json(f"/api/datasets/{source_id}", params={})
        return self.to_record(detail)

    def resolve(self, record: Record, selector: str | None = None) -> AccessPlan:
        """Every data file in the repo, pinned to the commit sha the record was read at."""
        if "siblings" not in record.source_metadata:
            record = self.get(record.id.partition(":")[2])
        meta = record.source_metadata
        repo_id: str = meta["id"]
        revision: str = meta.get("sha") or "main"
        siblings: list[dict[str, Any]] = meta.get("siblings") or []
        files = [
            PlannedFile(
                url=HttpUrl(f"{BASE_URL}/datasets/{repo_id}/resolve/{revision}/{name}"),
                filename=name,
            )
            for s in siblings
            for name in [str(s["rfilename"])]
            if Path(name).suffix.lower() in DATA_SUFFIXES and not Path(name).name.startswith(".")
        ]
        if not files:
            raise ValueError(f"{record.id} has no data files this adapter knows how to fetch")
        return AccessPlan(record_id=record.id, kind=Kind.DATASET, files=files)

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        if self._token is None and self._is_gated(plan.record_id):
            raise AccessRequired(
                f"{plan.record_id} is gated on the Hub. Accept its terms on the dataset page, "
                f"then set {TOKEN_ENV} or pass token= in the source config."
            )
        return download_all(self._client, plan, destination)

    def _is_gated(self, record_id: str) -> bool:
        return self.get(record_id.partition(":")[2]).access.gated

    def to_record(self, d: dict[str, Any]) -> Record:
        tags: list[str] = d.get("tags") or []
        repo_id: str = d["id"]
        gated = bool(d.get("gated"))  # False | "auto" | "manual"
        license_tags = _tag_values(tags, "license:")
        spdx = LICENSE_TAGS.get(license_tags[0]) if len(license_tags) == 1 else None
        page = HttpUrl(f"{BASE_URL}/datasets/{repo_id}")
        license = License(spdx=spdx, evidence_url=page if spdx else None)
        card: dict[str, Any] = d.get("cardData") or {}
        description = d.get("description")
        modality = _tag_values(tags, "modality:")
        return Record(
            id=f"{self.id}:{repo_id}",
            kind=Kind.DATASET,
            source=self.id,
            name=str(card.get("pretty_name") or repo_id),
            url=page,
            description=re.sub(r"\s+", " ", description).strip() if description else None,
            publisher=d.get("author"),
            license=license,
            rights=derive_rights(license),
            access=Access(authentication=gated, gated=gated),
            modality=modality[0] if len(modality) == 1 else None,
            tasks=_tag_values(tags, "task_categories:"),
            status=Status.RESTRICTED if gated else Status.IMPORTED,
            source_metadata=d,
        )

    def _get_json(self, path: str, *, params: dict[str, Any]) -> Any:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()
