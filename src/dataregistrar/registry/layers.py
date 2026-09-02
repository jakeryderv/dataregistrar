"""Layer resolution: built-in, then user, then project. Later layers win."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from platformdirs import user_config_path

APP_NAME = "dataregistrar"
PROJECT_DIR = "dataregistrar"


@dataclass(frozen=True)
class Layer:
    name: str
    path: Path

    @property
    def sources_file(self) -> Path:
        return self.path / "sources.yaml"

    @property
    def overlays_dir(self) -> Path:
        return self.path / "overlays"


def builtin_layer() -> Layer:
    with as_file(files("dataregistrar.builtin")) as path:
        return Layer("builtin", Path(path))


def user_layer() -> Layer:
    return Layer("user", user_config_path(APP_NAME))


def project_layer(cwd: Path | None = None) -> Layer:
    return Layer("project", (cwd or Path.cwd()) / PROJECT_DIR)


def default_layers(cwd: Path | None = None) -> list[Layer]:
    """All layers in resolution order, including ones whose directory does not exist yet."""
    return [builtin_layer(), user_layer(), project_layer(cwd)]
