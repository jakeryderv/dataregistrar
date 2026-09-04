from dataregistrar.adapters import Adapter, discover_adapters
from dataregistrar.adapters.huggingface import HuggingFaceAdapter
from dataregistrar.adapters.noaa import NOAAAdapter
from dataregistrar.adapters.uci import UCIAdapter


def test_uci_adapter_is_discoverable_via_entry_point() -> None:
    factories = discover_adapters()
    assert factories["uci"] is UCIAdapter
    assert factories["huggingface"] is HuggingFaceAdapter
    assert factories["noaa"] is NOAAAdapter


def test_uci_adapter_satisfies_protocol() -> None:
    assert isinstance(UCIAdapter(), Adapter)
    assert isinstance(HuggingFaceAdapter(), Adapter)
    assert isinstance(NOAAAdapter(), Adapter)
