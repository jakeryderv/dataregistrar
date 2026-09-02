"""Derive rights from licenses and check records against requirements."""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict

from dataregistrar._yaml import load_yaml
from dataregistrar.model import RIGHT_NAMES, Confidence, License, Record, Rights, RightValue

Requirement = dict[str, bool]


class LicenseTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    licenses: dict[str, dict[str, RightValue]]
    presets: dict[str, Requirement]


@cache
def load_table() -> LicenseTable:
    raw: Any = load_yaml(files("dataregistrar.policy").joinpath("licenses.yaml"))
    return LicenseTable.model_validate(raw)


def derive_rights(license: License, table: LicenseTable | None = None) -> Rights:
    """Rights implied by a license id. Unknown license, unknown rights. Always `imported`."""
    table = table or load_table()
    if license.spdx is None or license.spdx not in table.licenses:
        return Rights()
    return Rights(**table.licenses[license.spdx], confidence=Confidence.IMPORTED)


def preset(name: str, table: LicenseTable | None = None) -> Requirement:
    table = table or load_table()
    try:
        return table.presets[name]
    except KeyError:
        raise ValueError(
            f"unknown policy preset {name!r}; known: {sorted(table.presets)}"
        ) from None


class DatasetPolicyError(Exception):
    """A record does not satisfy a requirement. Carries the evidence for the decision."""

    def __init__(self, record: Record, right: str, wanted: bool, actual: RightValue) -> None:
        self.record = record
        self.right = right
        self.wanted = wanted
        self.actual = actual
        super().__init__(self._message())

    def _message(self) -> str:
        lic = self.record.license
        declared = lic.spdx or "unknown"
        evidence = f"evidence: {lic.evidence_url}" if lic.evidence_url else "no evidence"
        reason = (
            f"{self.right} is unknown for this record"
            if self.actual == "unknown"
            else f"{self.right}={self.actual} is declared, {self.wanted} was required"
        )
        return (
            f"Record:           {self.record.id}\n"
            f"Declared license: {declared} ({evidence}, "
            f"confidence: {self.record.rights.confidence})\n"
            f"Requested:        {self.right}={self.wanted}\n"
            f"Reason:           {reason}"
        )


def failing_right(record: Record, require: Requirement) -> tuple[str, bool, RightValue] | None:
    """First (right, wanted, actual) that fails, or None if every requirement holds."""
    for right, wanted in require.items():
        if right not in RIGHT_NAMES:
            raise ValueError(f"unknown right {right!r}; known: {RIGHT_NAMES}")
        actual = record.rights.value(right)
        if actual != wanted:
            return right, wanted, actual
    return None


def check(record: Record, require: Requirement) -> None:
    """Raise DatasetPolicyError unless every required right holds. Unknown never passes."""
    failure = failing_right(record, require)
    if failure is not None:
        raise DatasetPolicyError(record, *failure)


def satisfies(record: Record, require: Requirement) -> bool:
    return failing_right(record, require) is None
