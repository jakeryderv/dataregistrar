"""NCEI's dataset search service: NOAA's archive catalog, about a hundred curated entries."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import HttpUrl

from dataregistrar.model import Access, Kind, Record, Status

SEARCH_PATH = "/access/services/search/v1/datasets"
PUBLISHER = "NOAA National Centers for Environmental Information"


def search(client: httpx.Client, query: str | None, limit: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if query:
        params["text"] = query
    response = client.get(SEARCH_PATH, params=params)
    response.raise_for_status()
    results: list[dict[str, Any]] = response.json().get("results") or []
    return results


def to_record(source_id: str, d: dict[str, Any]) -> Record:
    """A catalog entry: describable and citable, but with no retrieval path in this adapter."""
    links: dict[str, list[dict[str, Any]]] = d.get("links") or {}
    landing = next(
        (link["url"] for link in links.get("other", []) if "landing" in str(link.get("name", ""))),
        None,
    )
    url = d.get("doiLink") or landing
    organization: dict[str, Any] = d.get("organization") or {}
    return Record(
        id=f"{source_id}:ncei/{d['id']}",
        kind=Kind.DATASET,
        source=source_id,
        name=str(d.get("name") or d["id"]),
        url=HttpUrl(url) if url else None,
        description=d.get("description"),
        publisher=str(organization.get("name") or PUBLISHER),
        access=Access(retrievable=False),
        status=Status.IMPORTED,
        source_metadata=d,
    )
