from pydantic import HttpUrl

from dataregistrar.model import Distribution, Kind, Overlay, Record, Release, Series, Status
from dataregistrar.registry.overlays import apply_overlay


def _release(period: str, revision: str) -> Release:
    name = f"StormEvents_d{period}_c{revision}.csv.gz"
    return Release(
        id=period,
        revision=revision,
        url=HttpUrl(f"https://x.test/{name}"),
        filename=f"{period}/{name}",
    )


def _record(*releases: Release) -> Record:
    return Record(
        id="noaa:ncei/storm-events",
        kind=Kind.RELEASE_SERIES,
        source="noaa",
        name="Storm Events",
        series=Series(releases=list(releases)),
    )


def _overlay(status: Status, **checksums: str) -> Overlay:
    return Overlay(
        canonical="noaa-storm-events",
        distributions=[Distribution(id="noaa:ncei/storm-events", checksums=checksums)],
        status=status,
    )


def test_reissued_period_is_linked_and_verified_record_goes_stale() -> None:
    old_name = "2024/StormEvents_d2024_c20250101.csv.gz"
    overlay = _overlay(Status.VERIFIED, **{old_name: "a" * 64})
    out = apply_overlay(
        _record(_release("2024", "20260728"), _release("2025", "20260819")), overlay
    )
    assert out.status is Status.STALE
    assert out.series is not None
    by_id = {r.id: r for r in out.series.releases}
    assert by_id["2024"].supersedes == old_name
    assert by_id["2025"].supersedes is None


def test_unchanged_recorded_release_stays_verified() -> None:
    current = _release("2024", "20260728")
    overlay = _overlay(Status.VERIFIED, **{current.filename: "a" * 64})
    out = apply_overlay(_record(current), overlay)
    assert out.status is Status.VERIFIED
    assert out.series is not None and out.series.releases[0].supersedes is None


def test_overlay_without_checksums_changes_nothing_about_releases() -> None:
    out = apply_overlay(_record(_release("2024", "20260728")), _overlay(Status.IMPORTED))
    assert out.status is Status.IMPORTED
    assert out.series is not None and out.series.releases[0].supersedes is None
