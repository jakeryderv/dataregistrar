"""Retrieve a release series end to end, fully offline: the listing and the files are both
served by a fixture transport, so nothing is recorded and no real data is fetched."""

import gzip
import hashlib
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from dataregistrar import federated
from dataregistrar.adapters import Adapter
from dataregistrar.adapters.noaa import BASE_URL, NOAAAdapter
from dataregistrar.adapters.noaa.collections.storm_events import LISTING
from dataregistrar.cli import app
from dataregistrar.model import Status
from dataregistrar.registry import Layer, Registry

LISTING_HTML = """<a href="StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz">x</a>
<a href="StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz">x</a>"""
CSV_2024 = gzip.compress(b"BEGIN_YEARMONTH,EVENT_TYPE\n202401,Hail\n")
CSV_2025 = gzip.compress(b"BEGIN_YEARMONTH,EVENT_TYPE\n202501,Tornado\n202502,Flood\n")
runner = CliRunner()


def _registry(tmp_path: Path, overlay: str | None = None) -> Registry:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == LISTING:
            return httpx.Response(200, text=LISTING_HTML)
        if url.endswith("d2024_c20260728.csv.gz"):
            return httpx.Response(200, content=CSV_2024)
        if url.endswith("d2025_c20260819.csv.gz"):
            return httpx.Response(200, content=CSV_2025)
        return httpx.Response(404)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))

    def factory(source_id: str, **_: Any) -> Adapter:
        return NOAAAdapter(source_id, client=client)

    layer = tmp_path / "layer"
    layer.mkdir()
    (layer / "sources.yaml").write_text("sources:\n  - {id: noaa, adapter: noaa}\n")
    if overlay:
        (layer / "overlays").mkdir()
        (layer / "overlays" / "noaa-storm-events.yaml").write_text(overlay)
    return Registry([Layer("t", layer)], factories={"noaa": factory})


def test_retrieve_latest_then_a_specific_year(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    latest = federated.retrieve(registry, "noaa:ncei/storm-events", destination=tmp_path / "out")
    assert latest.paths[0].name == "StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz"
    assert latest.paths[0].parent.name == "2025"
    assert latest.as_pandas().shape == (2, 2)

    y2024 = federated.retrieve(
        registry, "noaa:ncei/storm-events", destination=tmp_path / "out", release="2024"
    )
    assert y2024.as_pandas().shape == (1, 2)
    assert y2024.attribution.startswith("License: unknown")


def test_reissue_is_detected_through_a_verified_overlay(tmp_path: Path) -> None:
    old = "2024/StormEvents_details-ftp_v1.0_d2024_c20250101.csv.gz"
    overlay = (
        "canonical: noaa-storm-events\n"
        f'distributions: [{{id: "noaa:ncei/storm-events", checksums: {{"{old}": "{"a" * 64}"}}}}]\n'
        "license: {spdx: LicenseRef-US-Government-Work, evidence_url: 'https://x.test/terms', "
        "verified_at: 2026-09-01, verified_by: t}\n"
        "status: verified\n"
    )
    record = federated.get(_registry(tmp_path, overlay), "noaa:ncei/storm-events")
    assert record.status is Status.STALE
    assert record.series is not None
    assert next(r for r in record.series.releases if r.id == "2024").supersedes == old


def test_verified_checksum_is_enforced_per_release(tmp_path: Path) -> None:
    good = hashlib.sha256(CSV_2025).hexdigest()
    name = "2025/StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz"
    overlay = (
        "canonical: noaa-storm-events\n"
        f'distributions: [{{id: "noaa:ncei/storm-events", checksums: {{"{name}": "{good}"}}}}]\n'
        "status: verified\n"
    )
    local = federated.retrieve(
        _registry(tmp_path, overlay), "noaa:ncei/storm-events", destination=tmp_path / "o"
    )
    assert local.plan.files[0].sha256 == good


def test_cli_fetch_release_and_no_retrieval_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import dataregistrar

    registry = _registry(tmp_path)
    monkeypatch.setattr(dataregistrar, "default_registry", lambda: registry)
    result = runner.invoke(
        app, ["fetch", "noaa:ncei/storm-events", "--release", "2024", "--dest", str(tmp_path / "o")]
    )
    assert result.exit_code == 0, result.output
    assert "d2024_c20260728" in result.output

    result = runner.invoke(
        app, ["fetch", "noaa:ncei/storm-events", "--release", "1999", "--dest", str(tmp_path / "o")]
    )
    assert result.exit_code == 5
    assert "NoRetrievalPath" in result.output
