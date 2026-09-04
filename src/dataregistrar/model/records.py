"""Core record types. Pure data, no I/O. See docs/vision.md section 5.2."""

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Kind(StrEnum):
    """What sort of thing a record describes. Present on every record."""

    DATASET = "dataset"
    RELEASE_SERIES = "release-series"
    QUERY_API = "query-api"
    STREAM = "stream"


class Status(StrEnum):
    """Confidence level of a record. Imported must never look verified."""

    DISCOVERED = "discovered"
    IMPORTED = "imported"
    VERIFIED = "verified"
    STALE = "stale"
    RESTRICTED = "restricted"


class Confidence(StrEnum):
    """Who stands behind a rights claim."""

    IMPORTED = "imported"
    VERIFIED = "verified"


RightValue = bool | Literal["unknown"]
"""A single right. Missing or unclear is `unknown`, never inferred."""

RIGHT_NAMES: tuple[str, ...] = (
    "commercial_use",
    "redistribution",
    "derivatives",
    "model_training",
    "attribution_required",
    "share_alike",
)


class License(BaseModel):
    """A license claim and the evidence behind it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    spdx: str | None = None
    evidence_url: HttpUrl | None = None
    verified_at: date | None = None
    verified_by: str | None = None


class Rights(BaseModel):
    """Rights derived from a license or asserted by an overlay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commercial_use: RightValue = "unknown"
    redistribution: RightValue = "unknown"
    derivatives: RightValue = "unknown"
    model_training: RightValue = "unknown"
    attribution_required: RightValue = "unknown"
    share_alike: RightValue = "unknown"
    confidence: Confidence = Confidence.IMPORTED

    def value(self, right: str) -> RightValue:
        if right not in RIGHT_NAMES:
            raise KeyError(right)
        return getattr(self, right)


class Access(BaseModel):
    """What standing between a user and the bytes. Gated means the source must approve."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    authentication: bool = False
    gated: bool = False


class Record(BaseModel):
    """Common core of every record. Kind-specific access blocks are added later."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Kind
    source: str
    name: str
    url: HttpUrl | None = None
    description: str | None = None
    publisher: str | None = None
    cite_as: str | None = None
    canonical: str | None = None
    license: License = Field(default_factory=License)
    rights: Rights = Field(default_factory=Rights)
    access: Access = Field(default_factory=Access)
    modality: str | None = None
    tasks: list[str] = Field(default_factory=list)
    status: Status = Status.IMPORTED
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    """The provider's original metadata, preserved verbatim."""
