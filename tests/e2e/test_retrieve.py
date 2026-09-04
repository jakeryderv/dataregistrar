"""Retrieval end to end. Metadata comes from cassettes; file bodies come from a tiny
synthetic CSV served by a fixture transport, so no dataset content is ever recorded."""

import hashlib
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from dataregistrar import federated
from dataregistrar.adapters.uci import BASE_URL, UCIAdapter
from dataregistrar.cli import app
from dataregistrar.download import ChecksumMismatch
from dataregistrar.policy import DatasetPolicyError
from dataregistrar.registry import Layer, Registry
from dataregistrar.registry.layers import builtin_layer

FAKE_CSV = b"fixed_acidity,quality,color\n7.4,5,red\n6.3,6,white\n"
FAKE_SHA = hashlib.sha256(FAKE_CSV).hexdigest()
runner = CliRunner()


class FixtureTransport(httpx.BaseTransport):
    """Serve /static/ file downloads locally; pass API calls through to the cassette."""

    def __init__(self) -> None:
        self._real = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/static/"):
            return httpx.Response(200, content=FAKE_CSV)
        return self._real.handle_request(request)


def _registry(layers: list[Layer]) -> Registry:
    client = httpx.Client(base_url=BASE_URL, transport=FixtureTransport())

    def factory(source_id: str, **_: Any) -> UCIAdapter:
        return UCIAdapter(source_id, client=client)

    return Registry(layers, factories={"uci": factory})


def _overlay_layer(tmp_path: Path, sha256: str) -> Layer:
    (tmp_path / "overlays").mkdir(parents=True)
    (tmp_path / "overlays" / "wine.yaml").write_text(
        "canonical: uci-wine-quality\n"
        f'distributions: [{{id: "uci:186", role: official, sha256: {sha256}}}]\n'
        "license: {spdx: CC-BY-4.0, evidence_url: 'https://example.org', "
        "verified_at: 2026-09-02, verified_by: t}\n"
        "rights: {commercial_use: true, attribution_required: true, confidence: verified}\n"
        "status: verified\n"
    )
    (tmp_path / "sources.yaml").write_text("sources:\n  - {id: uci, adapter: uci}\n")
    return Layer("test", tmp_path)


@pytest.mark.vcr
def test_retrieve_verifies_overlay_checksum_and_loads(tmp_path: Path) -> None:
    registry = _registry([_overlay_layer(tmp_path / "layer", FAKE_SHA)])
    local = federated.retrieve(
        registry, "uci:186", destination=tmp_path / "out", policy="commercial"
    )
    assert [p.name for p in local.paths] == ["data.csv"]
    assert local.plan.files[0].sha256 == FAKE_SHA
    assert local.as_pandas().shape == (2, 3)
    assert "Attribution required." in local.attribution


@pytest.mark.vcr
def test_retrieve_rejects_file_that_does_not_match_overlay(tmp_path: Path) -> None:
    registry = _registry([builtin_layer()])  # real Wine Quality checksum, fake body
    with pytest.raises(ChecksumMismatch) as info:
        federated.retrieve(registry, "uci:186", destination=tmp_path / "out")
    assert info.value.actual == FAKE_SHA
    assert not (tmp_path / "out" / "data.csv").exists()


@pytest.mark.vcr
def test_retrieve_without_overlay_reports_no_expected_checksum(tmp_path: Path) -> None:
    (tmp_path / "layer").mkdir()
    (tmp_path / "layer" / "sources.yaml").write_text("sources:\n  - {id: uci, adapter: uci}\n")
    registry = _registry([Layer("bare", tmp_path / "layer")])
    local = federated.retrieve(registry, "uci:186", destination=tmp_path / "out")
    assert local.plan.files[0].sha256 is None
    assert (tmp_path / "out" / "data.csv").read_bytes() == FAKE_CSV


@pytest.mark.vcr
def test_policy_blocks_retrieve_before_any_download(tmp_path: Path) -> None:
    registry = _registry([builtin_layer()])
    with pytest.raises(DatasetPolicyError):
        federated.retrieve(registry, "uci:109", destination=tmp_path / "out", policy="commercial")
    assert not (tmp_path / "out").exists()


@pytest.mark.vcr
def test_cli_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import dataregistrar

    registry = _registry([_overlay_layer(tmp_path / "layer", FAKE_SHA)])
    monkeypatch.setattr(dataregistrar, "default_registry", lambda: registry)
    result = runner.invoke(app, ["fetch", "uci:186", "--dest", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert "checksum verified" in result.output
    assert "Attribution required." in result.output

    registry = _registry([builtin_layer()])
    monkeypatch.setattr(dataregistrar, "default_registry", lambda: registry)
    result = runner.invoke(app, ["fetch", "uci:186", "--dest", str(tmp_path / "out2")])
    assert result.exit_code == 3
    assert "ChecksumMismatch" in result.output
