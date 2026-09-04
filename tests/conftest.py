from pathlib import Path

import pytest

from dataregistrar.adapters.huggingface import HuggingFaceAdapter
from dataregistrar.adapters.noaa import NOAAAdapter
from dataregistrar.adapters.uci import UCIAdapter
from dataregistrar.registry import Layer, Registry
from dataregistrar.registry.layers import builtin_layer

CASSETTES = Path(__file__).parent / "cassettes"


@pytest.fixture(scope="session")
def vcr_cassette_dir() -> str:
    return str(CASSETTES)


@pytest.fixture(scope="session")
def vcr_config() -> dict[str, object]:
    return {"decode_compressed_response": True}


@pytest.fixture
def builtin_registry() -> Registry:
    """Built-in layer only, so tests are not affected by user or project layers."""
    return Registry(
        [builtin_layer()],
        factories={"uci": UCIAdapter, "huggingface": HuggingFaceAdapter, "noaa": NOAAAdapter},
    )


@pytest.fixture
def empty_registry(tmp_path: Path) -> Registry:
    """No sources, no overlays."""
    return Registry([Layer("empty", tmp_path)], factories={})
