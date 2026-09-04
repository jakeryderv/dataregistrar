"""One suite, run against every shipped adapter. Recorded HTTP only."""

import pytest

from dataregistrar.adapters import Adapter
from dataregistrar.adapters.uci import UCIAdapter
from dataregistrar.model import Rights, Status

CASES: list[tuple[Adapter, str, str, str]] = [
    # adapter, search query, expected id in results, native id for get
    (UCIAdapter(), "wine", "uci:186", "186"),
]


@pytest.mark.vcr
@pytest.mark.parametrize(("adapter", "query", "expected_id", "native_id"), CASES)
def test_search_returns_normalized_records(
    adapter: Adapter, query: str, expected_id: str, native_id: str
) -> None:
    records = adapter.search(query)
    assert expected_id in {r.id for r in records}
    for r in records:
        assert r.id.startswith(f"{adapter.id}:")
        assert r.source == adapter.id
        assert r.kind in adapter.kinds
        assert r.status in {Status.DISCOVERED, Status.IMPORTED}
        assert r.rights == Rights(), "adapters never guess rights"


@pytest.mark.vcr
@pytest.mark.parametrize(("adapter", "query", "expected_id", "native_id"), CASES)
def test_get_returns_imported_record_with_provider_metadata(
    adapter: Adapter, query: str, expected_id: str, native_id: str
) -> None:
    r = adapter.get(native_id)
    assert r.id == expected_id
    assert r.status is Status.IMPORTED
    assert r.name
    assert r.url is not None
    assert r.source_metadata, "provider metadata is preserved verbatim"
    assert r.rights == Rights()


@pytest.mark.vcr
@pytest.mark.parametrize(("adapter", "query", "expected_id", "native_id"), CASES)
def test_resolve_yields_a_plan_with_at_least_one_file(
    adapter: Adapter, query: str, expected_id: str, native_id: str
) -> None:
    plan = adapter.resolve(adapter.get(native_id))
    assert plan.record_id == expected_id
    assert plan.kind in adapter.kinds
    assert plan.files
    for planned in plan.files:
        assert planned.filename
        assert planned.sha256 is None, "adapters do not assert checksums; overlays do"
