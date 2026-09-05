"""GHCN-Daily by year: one gzipped CSV per year from 1763 on, every file rebuilt nightly.

Filenames carry only the year, so the listing's modification date is the revision. Because
every year's file changes daily, a verified overlay for this series goes stale the next day.
That is accurate: the content did change. The id matches NCEI's catalog entry so the catalog
hit and this collection merge into one record.
"""

from __future__ import annotations

import re

from dataregistrar.adapters.noaa.collections import DirectorySeries


class GHCNDaily(DirectorySeries):
    id = "ncei/daily-summaries"
    name = "Global Historical Climatology Network - Daily (GHCN-Daily), Version 3"
    description = (
        "Daily climate observations from land surface stations across the globe: temperature "
        "extremes, precipitation, snowfall, snow depth, and more. One file per year in the "
        "by_year layout, each row a station-element-day; all years rebuilt nightly."
    )
    cite_as = (
        "Menne, M.J., I. Durre, B. Korzeniewski, S. McNeill, K. Thomas, X. Yin, S. Anthony, "
        "R. Ray, R.S. Vose, B.E. Gleason, and T.G. Houston (2012): Global Historical Climatology "
        "Network - Daily (GHCN-Daily), Version 3. NOAA National Centers for Environmental "
        "Information. https://doi.org/10.7289/V5D21VHZ"
    )
    landing = (
        "https://www.ncei.noaa.gov/products/land-based-station/"
        "global-historical-climatology-network-daily"
    )
    listing = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/"
    pattern = re.compile(r'(?<=["/>])(?P<period>\d{4})\.csv\.gz')
    cadence = "daily; every year's file is rebuilt"
    revision_policy = "all files regenerate nightly; the listing modification date is the revision"
    keywords = (
        "ghcn",
        "daily summaries",
        "daily climate",
        "station",
        "precipitation",
        "temperature",
    )
    listing_dates = True
