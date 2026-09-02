from pathlib import Path

from dataregistrar.model import Confidence, Kind, Record, Status
from dataregistrar.registry import Layer, Registry


def _write_overlay(layer_dir: Path, text: str) -> None:
    (layer_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (layer_dir / "overlays" / "o.yaml").write_text(text)


def test_overlay_fields_win_and_confidence_becomes_verified(tmp_path: Path) -> None:
    _write_overlay(
        tmp_path,
        """
canonical: x-one
distributions: [{id: "x:1", role: official}]
license:
  spdx: CC-BY-4.0
  evidence_url: "https://example.org"
  verified_at: 2026-09-02
  verified_by: t
rights: {commercial_use: true, confidence: verified}
status: verified
""",
    )
    registry = Registry([Layer("t", tmp_path)], factories={})
    record = Record(id="x:1", kind=Kind.DATASET, source="x", name="orig")
    out = registry.annotate(record)
    assert out.canonical == "x-one"
    assert out.name == "orig", "overlay left name unset, record value kept"
    assert out.status is Status.VERIFIED
    assert out.license.spdx == "CC-BY-4.0"
    assert out.rights.commercial_use is True
    assert out.rights.confidence is Confidence.VERIFIED
    assert registry.overlays.for_record("x:1") is not None
    assert registry.overlays.for_record("x:1").layer == "t"  # type: ignore[union-attr]


def test_later_layer_overrides_earlier(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    _write_overlay(a, 'canonical: c\ndistributions: [{id: "x:1"}]\nname: from-a\n')
    _write_overlay(b, 'canonical: c\ndistributions: [{id: "x:1"}]\nname: from-b\n')
    registry = Registry([Layer("a", a), Layer("b", b)], factories={})
    record = Record(id="x:1", kind=Kind.DATASET, source="x", name="orig")
    assert registry.annotate(record).name == "from-b"


def test_record_without_overlay_is_unchanged(tmp_path: Path) -> None:
    registry = Registry([Layer("t", tmp_path)], factories={})
    record = Record(id="x:9", kind=Kind.DATASET, source="x", name="n")
    assert registry.annotate(record) == record
