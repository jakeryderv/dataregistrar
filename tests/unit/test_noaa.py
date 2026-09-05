import json
from typing import Any

import httpx
import pytest

from dataregistrar.adapters import NoRetrievalPath
from dataregistrar.adapters.noaa import BASE_URL, NOAAAdapter
from dataregistrar.adapters.noaa.collections.ghcn_daily import GHCNDaily
from dataregistrar.adapters.noaa.collections.storm_events import LISTING
from dataregistrar.model import Kind, Rights, Status

_NAMES = [
    "StormEvents_details-ftp_v1.0_d1950_c20260323.csv.gz",
    "StormEvents_fatalities-ftp_v1.0_d1950_c20260323.csv.gz",
    "StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz",
    "StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz",
]
LISTING_HTML = (
    "<html><body><pre>\n" + "".join(f'<a href="{n}">{n}</a>\n' for n in _NAMES) + "</pre>"
)

CATALOG: dict[str, Any] = {
    "count": 2,
    "results": [
        {
            "id": "storm-data-publication",
            "name": "Storm Data Publication",
            "description": "Monthly publication.",
            "doiLink": "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C01036",
            "organization": {"name": "NOAA National Centers for Environmental Information"},
            "links": {
                "other": [{"name": "ncei dataset landing page", "url": "https://x.test/landing"}]
            },
        },
        {
            "id": "no-doi",
            "name": "No DOI",
            "links": {
                "other": [{"name": "ncei dataset landing page", "url": "https://x.test/landing2"}]
            },
        },
        {"id": "daily-summaries", "name": "GHCN-Daily from the catalog", "links": {}},
    ],
}
GHCN_HTML = (
    '<tr><td><a href="1763.csv.gz">1763.csv.gz</a></td><td>2026-09-04 23:37</td></tr>'
    '<tr><td><a href="2026.csv.gz">2026.csv.gz</a></td><td>2026-09-04 23:36</td></tr>'
)


def _adapter(calls: list[str] | None = None) -> NOAAAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if str(request.url) == LISTING:
            return httpx.Response(200, text=LISTING_HTML)
        if str(request.url) == GHCNDaily.listing:
            return httpx.Response(200, text=GHCN_HTML)
        if request.url.path.startswith("/access/services/search/v1/datasets"):
            return httpx.Response(200, json=CATALOG)
        return httpx.Response(404)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return NOAAAdapter(client=client)


def test_search_puts_matching_collection_first_then_catalog_hits() -> None:
    records = _adapter().search("storm")
    assert [r.id for r in records][:1] == ["noaa:ncei/storm-events"]
    assert "noaa:ncei/storm-data-publication" in {r.id for r in records}
    summary = records[0]
    assert summary.kind is Kind.RELEASE_SERIES
    assert summary.status is Status.DISCOVERED
    assert summary.series is not None and summary.series.releases == []
    catalog_hit = next(r for r in records if r.id == "noaa:ncei/storm-data-publication")
    assert catalog_hit.access.retrievable is False
    assert catalog_hit.status is Status.IMPORTED
    assert catalog_hit.rights == Rights()


def test_search_without_match_returns_catalog_only() -> None:
    records = _adapter().search("ocean")
    assert all(r.id != "noaa:ncei/storm-events" for r in records)


def test_catalog_hit_claimed_by_a_collection_merges_into_it() -> None:
    records = _adapter().search("ocean")  # keywords do not match GHCN; the catalog id does
    ghcn = [r for r in records if r.id == "noaa:ncei/daily-summaries"]
    assert len(ghcn) == 1, "one record, not a collection plus a catalog hit"
    assert ghcn[0].kind is Kind.RELEASE_SERIES
    assert ghcn[0].name.startswith("Global Historical Climatology Network - Daily")


def test_ghcn_daily_uses_listing_dates_as_revisions() -> None:
    record = _adapter().get("ncei/daily-summaries")
    assert record.series is not None
    latest = record.series.latest()
    assert latest.id == "2026" and latest.revision == "20260904"
    assert latest.filename == "2026/20260904/2026.csv.gz"


def test_get_collection_lists_details_only_and_orders_by_period() -> None:
    record = _adapter().get("ncei/storm-events")
    assert record.status is Status.IMPORTED
    assert record.series is not None
    assert [r.id for r in record.series.releases] == ["1950", "2024", "2025"]
    latest = record.series.latest()
    assert latest.revision == "20260819"
    assert str(latest.published) == "2026-08-19"
    assert latest.filename == "2025/StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz"
    assert str(latest.url) == LISTING + "StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz"


def test_get_catalog_entry_by_id_and_unknown_id() -> None:
    adapter = _adapter()
    record = adapter.get("ncei/no-doi")
    assert record.name == "No DOI"
    assert str(record.url) == "https://x.test/landing2"
    with pytest.raises(LookupError):
        adapter.get("ncei/nope")
    with pytest.raises(LookupError):
        adapter.get("nws/anything")


def test_resolve_latest_specific_and_missing_release() -> None:
    adapter = _adapter()
    record = adapter.get("ncei/storm-events")
    assert adapter.resolve(record).files[0].filename.startswith("2025/")
    assert adapter.resolve(record, "2024").files[0].filename.startswith("2024/")
    with pytest.raises(KeyError, match=r"1950\.\.2025"):
        adapter.resolve(record, "1999")


def test_resolve_from_summary_fetches_listing_first() -> None:
    calls: list[str] = []
    adapter = _adapter(calls)
    summary = adapter.search("storm")[0]
    plan = adapter.resolve(summary)
    assert plan.files[0].filename.startswith("2025/")
    assert LISTING in calls


def test_catalog_entries_have_no_retrieval_path() -> None:
    adapter = _adapter()
    record = next(r for r in adapter.search("storm") if r.id == "noaa:ncei/storm-data-publication")
    with pytest.raises(NoRetrievalPath, match="C01036"):
        adapter.resolve(record)


def test_catalog_record_round_trips_as_json() -> None:
    record = _adapter().get("ncei/storm-data-publication")
    assert json.loads(record.model_dump_json())["source_metadata"]["id"] == "storm-data-publication"


def test_collection_matching_is_lenient() -> None:
    from dataregistrar.adapters.noaa.collections.storm_events import StormEvents

    assert StormEvents().matches("Storm Events")
    assert StormEvents().matches("tornado")
    assert not StormEvents().matches("sea surface temperature")
