"""Search → overlay → policy, end to end, against recorded UCI responses."""

import pytest
from typer.testing import CliRunner

from dataregistrar import federated as search_module
from dataregistrar.cli import app
from dataregistrar.model import Confidence, Status
from dataregistrar.policy import DatasetPolicyError
from dataregistrar.registry import Registry

runner = CliRunner()


@pytest.mark.vcr
def test_commercial_search_keeps_verified_wine_quality_and_drops_the_rest(
    builtin_registry: Registry,
) -> None:
    everything = search_module.search(builtin_registry, "wine")
    commercial = search_module.search(builtin_registry, "wine", policy="commercial")

    assert {r.id for r in everything} >= {"uci:109", "uci:186"}
    assert [r.id for r in commercial] == ["uci:186"]

    wine_quality = commercial[0]
    assert wine_quality.status is Status.VERIFIED
    assert wine_quality.canonical == "uci-wine-quality"
    assert wine_quality.license.spdx == "CC-BY-4.0"
    assert wine_quality.rights.confidence is Confidence.VERIFIED

    unverified = next(r for r in everything if r.id == "uci:109")
    assert unverified.status is Status.DISCOVERED
    assert unverified.rights.commercial_use == "unknown"


@pytest.mark.vcr
def test_get_with_policy_fails_clearly_for_unverified_record(builtin_registry: Registry) -> None:
    with pytest.raises(DatasetPolicyError, match="commercial_use is unknown"):
        search_module.get(builtin_registry, "uci:109", policy="commercial")


@pytest.mark.vcr
def test_min_status_verified_hides_imported_results(builtin_registry: Registry) -> None:
    results = search_module.search(builtin_registry, "wine", min_status=Status.VERIFIED)
    assert [r.id for r in results] == ["uci:186"]


@pytest.mark.vcr
def test_cli_search_and_get(monkeypatch: pytest.MonkeyPatch, builtin_registry: Registry) -> None:
    import dataregistrar

    monkeypatch.setattr(dataregistrar, "default_registry", lambda: builtin_registry)

    result = runner.invoke(app, ["search", "wine", "--policy", "commercial"])
    assert result.exit_code == 0, result.output
    assert "uci:186" in result.output
    assert "uci:109" not in result.output

    result = runner.invoke(app, ["get", "uci:186"])
    assert result.exit_code == 0, result.output
    assert "CC-BY-4.0" in result.output
    assert "verified" in result.output

    result = runner.invoke(app, ["get", "uci:109", "--policy", "commercial"])
    assert result.exit_code == 2
    assert "DatasetPolicyError" in result.output
