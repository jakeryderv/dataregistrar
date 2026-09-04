"""Search across UCI and Hugging Face together, against recorded responses."""

import pytest

from dataregistrar import federated
from dataregistrar.model import Confidence, Status
from dataregistrar.registry import Registry


@pytest.mark.vcr
def test_both_sources_contribute_and_confidence_is_visible(builtin_registry: Registry) -> None:
    results = federated.search(builtin_registry, "wine")
    by_source = {r.source for r in results}
    assert by_source == {"uci", "hf"}

    hub = next(r for r in results if r.id == "hf:codesignal/wine-quality")
    assert hub.license.spdx == "CC-BY-4.0"
    assert hub.rights.commercial_use is True
    assert hub.rights.confidence is Confidence.IMPORTED
    assert hub.status is Status.IMPORTED

    uci = next(r for r in results if r.id == "uci:186")
    assert uci.rights.confidence is Confidence.VERIFIED


@pytest.mark.vcr
def test_policy_passes_imported_rights_but_min_status_separates_them(
    builtin_registry: Registry,
) -> None:
    commercial = {r.id for r in federated.search(builtin_registry, "wine", policy="commercial")}
    assert {"uci:186", "hf:codesignal/wine-quality"} <= commercial

    verified = [
        r.id for r in federated.search(builtin_registry, "wine", min_status=Status.VERIFIED)
    ]
    assert verified == ["uci:186"]


@pytest.mark.vcr
def test_sources_filter_narrows_the_fan_out(builtin_registry: Registry) -> None:
    only_hub = federated.search(builtin_registry, "wine", sources=["hf"])
    assert only_hub and all(r.source == "hf" for r in only_hub)
