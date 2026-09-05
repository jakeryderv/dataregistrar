"""NCEI Storm Events Database: one gzipped CSV of event details per year, re-issued as needed.

Filenames carry the year and the creation date, e.g.
`StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz`. Recent years are refreshed roughly
monthly; older years get re-issued sporadically, which is why overlays record checksums per
issued filename and a changed filename for a known year marks the record stale.
"""

from __future__ import annotations

import re

from dataregistrar.adapters.noaa.collections import DirectorySeries

LISTING = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
PATTERN = re.compile(
    r"StormEvents_details-ftp_v1\.0_d(?P<period>\d{4})_c(?P<revision>\d{8})\.csv\.gz"
)


class StormEvents(DirectorySeries):
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
    landing = "https://www.ncei.noaa.gov/access/storm-events-database/"
    listing = LISTING
    pattern = PATTERN
    cadence = "monthly for recent years"
    revision_policy = "prior years are re-issued in place with a new creation date"
    keywords = ("storm", "storm events", "severe weather", "tornado", "hail", "wind", "flood")
