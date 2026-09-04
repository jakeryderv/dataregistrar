"""NCEI Storm Events Database: one gzipped CSV of event details per year, re-issued as needed.

Filenames carry the year and the creation date, e.g.
`StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz`. Recent years are refreshed roughly
monthly; older years get re-issued sporadically, which is why overlays record checksums per
issued filename and a changed filename for a known year marks the record stale.
"""

from __future__ import annotations

import re

import httpx
from pydantic import HttpUrl

from dataregistrar.adapters.noaa.series import list_releases
from dataregistrar.model import AccessPlan, Kind, PlannedFile, Record, Series, Status

LISTING = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
PATTERN = re.compile(
    r"StormEvents_details-ftp_v1\.0_d(?P<period>\d{4})_c(?P<revision>\d{8})\.csv\.gz"
)
LANDING = "https://www.ncei.noaa.gov/access/storm-events-database/"
KEYWORDS = ("storm", "storm events", "severe weather", "tornado", "hail", "wind", "flood")


class StormEvents:
    id = "ncei/storm-events"
    name = "Storm Events Database"
    description = (
        "Occurrences of storms and other significant weather phenomena in the United States "
        "since 1950, as reported by the National Weather Service: tornadoes, thunderstorm wind, "
        "hail, floods, and more. Event details, one file per year. Fatalities and locations "
        "files are not fetched by this collection yet."
    )
    cite_as = (
        "NOAA National Centers for Environmental Information. Storm Events Database. "
        "https://www.ncei.noaa.gov/access/storm-events-database/"
    )

    def matches(self, query: str) -> bool:
        q = query.lower()
        return any(k in q or q in k for k in KEYWORDS)

    def _record(self, source_id: str, series: Series, status: Status) -> Record:
        return Record(
            id=f"{source_id}:{self.id}",
            kind=Kind.RELEASE_SERIES,
            source=source_id,
            name=self.name,
            url=HttpUrl(LANDING),
            description=self.description,
            publisher="NOAA National Centers for Environmental Information",
            cite_as=self.cite_as,
            modality="tabular",
            series=series,
            status=status,
            source_metadata={
                "listing": LISTING,
                "pattern": PATTERN.pattern,
                "files": len(series.releases),
            },
        )

    def _series(self, releases: list[object] | None = None) -> Series:
        return Series(
            cadence="monthly for recent years",
            revision_policy="prior years are re-issued in place with a new creation date",
            releases=releases or [],  # type: ignore[arg-type]
        )

    def summary(self, source_id: str) -> Record:
        return self._record(source_id, self._series(), Status.DISCOVERED)

    def detail(self, client: httpx.Client, source_id: str) -> Record:
        releases = list_releases(client, LISTING, PATTERN)
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
