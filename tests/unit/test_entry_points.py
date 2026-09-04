from dataregistrar.adapters import Adapter, discover_adapters
from dataregistrar.adapters.huggingface import HuggingFaceAdapter
from dataregistrar.adapters.uci import UCIAdapter


def test_uci_adapter_is_discoverable_via_entry_point() -> None:
    factories = discover_adapters()
    assert factories["uci"] is UCIAdapter
    assert factories["huggingface"] is HuggingFaceAdapter


def test_uci_adapter_satisfies_protocol() -> None:
    assert isinstance(UCIAdapter(), Adapter)
    assert isinstance(HuggingFaceAdapter(), Adapter)
