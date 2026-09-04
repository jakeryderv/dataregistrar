"""Access plans: what an adapter will fetch for a record. Pure data."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from dataregistrar.model.records import Kind


class PlannedFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: HttpUrl
    filename: str
    sha256: str | None = None
    """Expected checksum, if an overlay or the source recorded one."""


class AccessPlan(BaseModel):
    """Everything needed to retrieve a `dataset` record. Other kinds get their own plans."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    kind: Kind
    files: list[PlannedFile] = Field(min_length=1)
