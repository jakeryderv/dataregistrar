"""Single place that touches ruamel, whose public API is untyped."""

from __future__ import annotations

from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def load_yaml(source: Path | Traversable) -> Any:
    with source.open("r", encoding="utf-8") as handle:
        return YAML(typ="safe").load(handle)  # pyright: ignore[reportUnknownMemberType]


def dump_yaml(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 100
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)  # pyright: ignore[reportUnknownMemberType]
