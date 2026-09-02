"""Core record types. Pure data, no I/O. See docs/vision.md section 5.2."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, HttpUrl


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


class Record(BaseModel):
    """Minimal common core of a record. Kind-specific fields are added later."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Kind
    source: str
    name: str
    url: HttpUrl | None = None
    description: str | None = None
    status: Status = Status.IMPORTED
