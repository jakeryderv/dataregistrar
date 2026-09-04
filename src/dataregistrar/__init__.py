"""Provider-agnostic catalog and access layer for public data."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from dataregistrar import federated as _federated
from dataregistrar.download import ChecksumMismatch
from dataregistrar.model import AccessPlan, Kind, License, Record, Rights, Status
from dataregistrar.policy import DatasetPolicyError, Requirement
from dataregistrar.registry import Registry
from dataregistrar.representations import LocalDataset

__version__ = version("dataregistrar")

_default: Registry | None = None


def default_registry() -> Registry:
    global _default
    if _default is None:
        _default = Registry.default()
    return _default


def search(
    query: str,
    *,
    sources: list[str] | None = None,
    policy: str | None = None,
    require: Requirement | None = None,
    min_status: Status | None = None,
    fresh: bool = False,
) -> list[Record]:
    return _federated.search(
        default_registry(),
        query,
        sources=sources,
        policy=policy,
        require=require,
        min_status=min_status,
        fresh=fresh,
    )


def get(
    record_id: str,
    *,
    policy: str | None = None,
    require: Requirement | None = None,
    fresh: bool = False,
) -> Record:
    return _federated.get(
        default_registry(), record_id, policy=policy, require=require, fresh=fresh
    )


def resolve(record_id: str, *, release: str | None = None) -> AccessPlan:
    return _federated.resolve(default_registry(), record_id, release=release)


def retrieve(
    record_id: str,
    *,
    destination: Path | None = None,
    policy: str | None = None,
    require: Requirement | None = None,
    release: str | None = None,
) -> LocalDataset:
    return _federated.retrieve(
        default_registry(),
        record_id,
        destination=destination,
        policy=policy,
        require=require,
        release=release,
    )


__all__ = [
    "AccessPlan",
    "ChecksumMismatch",
    "DatasetPolicyError",
    "Kind",
    "License",
    "LocalDataset",
    "Record",
    "Registry",
    "Rights",
    "Status",
    "__version__",
    "default_registry",
    "get",
    "resolve",
    "retrieve",
    "search",
]
