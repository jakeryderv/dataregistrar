"""Overlay: human-reviewed facts pinned to one or more records. See vision.md 5.3."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dataregistrar.model.records import Kind, License, Rights, Status


class Distribution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: Literal["official", "mirror", "conversion", "subset"] = "official"
    modifications: str | None = None
    sha256: str | None = None
    """Checksum when the distribution is a single file."""
    checksums: dict[str, str] = Field(default_factory=dict[str, str])
    """Per-file checksums keyed by the planned filename, for multi-file distributions."""


class Overlay(BaseModel):
    """One overlay file. Every field except `canonical` and `distributions` is optional."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical: str
    distributions: list[Distribution] = Field(min_length=1)
    kind: Kind | None = None
    name: str | None = None
    publisher: str | None = None
    cite_as: str | None = None
    license: License | None = None
    rights: Rights | None = None
    status: Status | None = None
    layer: str | None = None
    """Which layer this overlay came from. Set by the loader, not the file."""
