from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import HttpUrl

from dataregistrar import curate, federated
from dataregistrar.adapters import Adapter
from dataregistrar.model import AccessPlan, Confidence, Kind, PlannedFile, Record, Status
from dataregistrar.registry import Layer, Registry

BODY = b"a,b\n1,2\n"


class FakeAdapter:
    id = "fake"
    kinds = frozenset({Kind.DATASET})

    def __init__(self, *, cite: bool = True, fail_retrieve: bool = False) -> None:
        self.cite = cite
        self.fail_retrieve = fail_retrieve

    def search(self, query: str) -> list[Record]:
        return [self.get("1")]

    def get(self, source_id: str) -> Record:
        return Record(
            id=f"fake:{source_id}",
            kind=Kind.DATASET,
            source="fake",
            name="Some Data Set",
            url=HttpUrl("https://fake.test/ds/1"),
            publisher="Fake Org",
            cite_as="Fake Org (2026). Some Data Set." if self.cite else None,
        )

    def resolve(self, record: Record, selector: str | None = None) -> AccessPlan:
        return AccessPlan(
            record_id=record.id,
            kind=Kind.DATASET,
            files=[PlannedFile(url=HttpUrl("https://fake.test/d.csv"), filename="d.csv")],
        )

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        if self.fail_retrieve:
            raise RuntimeError("boom")
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "d.csv"
        path.write_bytes(BODY)
        return [path]


def _registry(tmp_path: Path, adapter: FakeAdapter | None = None) -> tuple[Registry, Layer]:
    layer_dir = tmp_path / "layer"
    layer_dir.mkdir()
    (layer_dir / "sources.yaml").write_text("sources:\n  - {id: fake, adapter: fake}\n")
    inner = adapter or FakeAdapter()

    def factory(source_id: str, **_: Any) -> Adapter:
        return inner

    layer = Layer("test", layer_dir)
    return Registry([layer], factories={"fake": factory}), layer


def test_create_prefills_from_record_and_stays_imported(tmp_path: Path) -> None:
    registry, layer = _registry(tmp_path)
    path = curate.create_overlay(registry, "fake:1", layer=layer)
    assert path == layer.overlays_dir / "fake-some-data-set.yaml"
    overlay = curate.load_overlay(path)
    assert overlay.canonical == "fake-some-data-set"
    assert overlay.name == "Some Data Set"
    assert overlay.status is Status.IMPORTED
    assert overlay.license is None
    assert [d.id for d in overlay.distributions] == ["fake:1"]
    with pytest.raises(FileExistsError):
        curate.create_overlay(registry, "fake:1", layer=layer)


def test_verify_passes_and_writes_verified_overlay(tmp_path: Path) -> None:
    registry, layer = _registry(tmp_path)
    path = curate.create_overlay(
        registry, "fake:1", layer=layer, spdx="CC-BY-4.0", evidence_url="https://fake.test/lic"
    )
    result = curate.verify_overlay(
        registry, path, by="tester", today=date(2026, 9, 3), url_ok=lambda _: True
    )
    assert result.passed, [c for c in result.checks if not c.ok]

    overlay = curate.load_overlay(path)
    assert overlay.status is Status.VERIFIED
    assert overlay.license is not None
    assert overlay.license.verified_by == "tester"
    assert overlay.license.verified_at == date(2026, 9, 3)
    assert overlay.rights is not None
    assert overlay.rights.commercial_use is True
    assert overlay.rights.confidence is Confidence.VERIFIED
    assert overlay.cite_as == "Fake Org (2026). Some Data Set."
    official = overlay.distributions[0]
    assert official.sha256 is not None and official.checksums["d.csv"] == official.sha256

    # the fresh registry now attaches that checksum to retrieval plans
    fresh = Registry([layer], factories=registry.factories)
    plan = federated.resolve(fresh, "fake:1")
    assert plan.files[0].sha256 == official.sha256


@pytest.mark.parametrize(
    ("setup", "failing"),
    [
        ({"spdx": None}, "license"),
        ({"evidence_url": None}, "license"),
        ({"bad_url": "https://fake.test/lic"}, "license"),
        ({"bad_url": "https://fake.test/ds/1"}, "source url"),
        ({"adapter": FakeAdapter(fail_retrieve=True)}, "retrieval"),
        ({"adapter": FakeAdapter(cite=False)}, "citation"),
        ({"adapter": FakeAdapter(cite=False), "cite_as": "Given (2026)", "expect_pass": True}, "-"),
        ({"by": ""}, "reviewer"),
    ],
)
def test_verify_fails_one_check_and_leaves_file_untouched(
    tmp_path: Path, setup: dict[str, Any], failing: str
) -> None:
    registry, layer = _registry(tmp_path, setup.get("adapter"))
    path = curate.create_overlay(
        registry,
        "fake:1",
        layer=layer,
        spdx=setup.get("spdx", "CC-BY-4.0"),
        evidence_url=setup.get("evidence_url", "https://fake.test/lic"),
        cite_as=setup.get("cite_as"),
    )
    before = path.read_text()
    bad = setup.get("bad_url")
    result = curate.verify_overlay(
        registry, path, by=setup.get("by", "tester"), url_ok=lambda url: url != bad
    )
    if setup.get("expect_pass"):
        assert result.passed
        return
    assert not result.passed
    assert next(c.name for c in result.checks if not c.ok) == failing
    assert path.read_text() == before
    assert curate.load_overlay(path).status is Status.IMPORTED


def test_slug_and_default_canonical() -> None:
    assert curate.slug("  Wine Quality (Red & White) ") == "wine-quality-red-white"
