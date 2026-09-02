"""Federated search: fan out to sources, annotate with overlays, filter by policy."""

from __future__ import annotations

from collections.abc import Iterable

from dataregistrar.model import Record, Status
from dataregistrar.policy import Requirement, check, preset, satisfies
from dataregistrar.registry import Registry

_STATUS_RANK: dict[Status, int] = {
    Status.DISCOVERED: 0,
    Status.IMPORTED: 1,
    Status.STALE: 1,
    Status.RESTRICTED: 1,
    Status.VERIFIED: 2,
}


def _requirement(policy: str | None, require: Requirement | None) -> Requirement:
    merged: Requirement = dict(preset(policy)) if policy else {}
    if require:
        merged.update(require)
    return merged


def _meets_status(record: Record, min_status: Status | None) -> bool:
    return min_status is None or _STATUS_RANK[record.status] >= _STATUS_RANK[min_status]


def search(
    registry: Registry,
    query: str,
    *,
    sources: Iterable[str] | None = None,
    policy: str | None = None,
    require: Requirement | None = None,
    min_status: Status | None = None,
) -> list[Record]:
    """Search every enabled source (or the given subset), annotate, then filter."""
    ids = list(sources) if sources is not None else registry.source_ids
    requirement = _requirement(policy, require)
    results: list[Record] = []
    for source_id in ids:
        for record in registry.adapter(source_id).search(query):
            annotated = registry.annotate(record)
            if _meets_status(annotated, min_status) and satisfies(annotated, requirement):
                results.append(annotated)
    return results


def get(
    registry: Registry,
    record_id: str,
    *,
    policy: str | None = None,
    require: Requirement | None = None,
) -> Record:
    """Fetch one record by `source:id`, annotate, and enforce any requirement."""
    source_id, _, native_id = record_id.partition(":")
    if not native_id:
        raise ValueError(f"record id must look like 'source:id', got {record_id!r}")
    record = registry.annotate(registry.adapter(source_id).get(native_id))
    check(record, _requirement(policy, require))
    return record
