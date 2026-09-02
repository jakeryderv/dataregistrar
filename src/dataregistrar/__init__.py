"""Provider-agnostic catalog and access layer for public data."""

from __future__ import annotations

from importlib.metadata import version

from dataregistrar import federated as _federated
from dataregistrar.model import Kind, License, Record, Rights, Status
from dataregistrar.policy import DatasetPolicyError, Requirement
from dataregistrar.registry import Registry

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
) -> list[Record]:
    return _federated.search(
        default_registry(),
        query,
        sources=sources,
        policy=policy,
        require=require,
        min_status=min_status,
    )


def get(record_id: str, *, policy: str | None = None, require: Requirement | None = None) -> Record:
    return _federated.get(default_registry(), record_id, policy=policy, require=require)


__all__ = [
    "DatasetPolicyError",
    "Kind",
    "License",
    "Record",
    "Registry",
    "Rights",
    "Status",
    "__version__",
    "default_registry",
    "get",
    "search",
]
