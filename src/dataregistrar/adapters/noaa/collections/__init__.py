"""Collections: one delivery mechanism each. Internal to the NOAA adapter."""

from __future__ import annotations

import re
from typing import ClassVar, Protocol

import httpx
from pydantic import HttpUrl

from dataregistrar.adapters.noaa.series import list_releases
from dataregistrar.model import AccessPlan, Kind, PlannedFile, Record, Series, Status

PUBLISHER = "NOAA National Centers for Environmental Information"


class Collection(Protocol):
    id: str
    """Service-qualified id, e.g. `ncei/storm-events`. Record id is `<source>:<this>`.
    When NCEI's catalog has an entry for the same dataset, use the catalog's id so the two merge."""

    def matches(self, query: str) -> bool: ...

    def summary(self, source_id: str) -> Record:
        """Cheap record with no network call. Used in search results."""
        ...

    def detail(self, client: httpx.Client, source_id: str) -> Record:
        """Full record, releases listed."""
        ...

    def resolve(
        self, client: httpx.Client, source_id: str, record: Record, selector: str | None
    ) -> AccessPlan: ...


class DirectorySeries:
    """A `release-series` served from a file directory. Subclasses set the class attributes."""

    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    cite_as: ClassVar[str]
    landing: ClassVar[str]
    listing: ClassVar[str]
    pattern: ClassVar[re.Pattern[str]]
    cadence: ClassVar[str]
    revision_policy: ClassVar[str]
    keywords: ClassVar[tuple[str, ...]]
    listing_dates: ClassVar[bool] = False

    def matches(self, query: str) -> bool:
        q = query.lower()
        return any(k in q or q in k for k in self.keywords)

    def _record(self, source_id: str, series: Series, status: Status) -> Record:
        return Record(
            id=f"{source_id}:{self.id}",
            kind=Kind.RELEASE_SERIES,
            source=source_id,
            name=self.name,
            url=HttpUrl(self.landing),
            description=self.description,
            publisher=PUBLISHER,
            cite_as=self.cite_as,
            modality="tabular",
            series=series,
            status=status,
            source_metadata={
                "listing": self.listing,
                "pattern": self.pattern.pattern,
                "files": len(series.releases),
            },
        )

    def _series(self, releases: list[object] | None = None) -> Series:
        return Series(
            cadence=self.cadence,
            revision_policy=self.revision_policy,
            releases=releases or [],  # type: ignore[arg-type]
        )

    def summary(self, source_id: str) -> Record:
        return self._record(source_id, self._series(), Status.DISCOVERED)

    def detail(self, client: httpx.Client, source_id: str) -> Record:
        releases = list_releases(
            client, self.listing, self.pattern, listing_dates=self.listing_dates
        )
        return self._record(source_id, self._series(list(releases)), Status.IMPORTED)

    def resolve(
        self, client: httpx.Client, source_id: str, record: Record, selector: str | None
    ) -> AccessPlan:
        if record.series is None or not record.series.releases:
            record = self.detail(client, source_id)
        assert record.series is not None
        release = (
            record.series.latest()
            if selector in (None, "latest")
            else record.series.release(str(selector))
        )
        return AccessPlan(
            record_id=record.id,
            kind=Kind.RELEASE_SERIES,
            files=[PlannedFile(url=release.url, filename=release.filename)],
        )
