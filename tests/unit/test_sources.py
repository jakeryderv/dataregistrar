from pathlib import Path

import pytest

from dataregistrar.registry import Layer, Registry


def test_later_layer_can_disable_a_source(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "sources.yaml").write_text("sources:\n  - {id: uci, adapter: uci}\n")
    (b / "sources.yaml").write_text("sources:\n  - {id: uci, adapter: uci, enabled: false}\n")
    assert Registry([Layer("a", a)], factories={}).source_ids == ["uci"]
    assert Registry([Layer("a", a), Layer("b", b)], factories={}).source_ids == []


def test_missing_adapter_is_a_clear_error(tmp_path: Path) -> None:
    (tmp_path / "sources.yaml").write_text("sources:\n  - {id: lake, adapter: lakehouse}\n")
    registry = Registry([Layer("t", tmp_path)], factories={})
    with pytest.raises(LookupError, match="needs adapter 'lakehouse'"):
        registry.adapter("lake")


def test_builtin_layer_ships_uci_and_the_wine_overlay() -> None:
    registry = Registry.default(cwd=Path("/nonexistent"))
    assert "uci" in registry.source_ids
    assert registry.overlays.for_record("uci:186") is not None
