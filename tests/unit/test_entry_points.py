from dataregistrar.adapters import Adapter, discover_adapters
from dataregistrar.adapters.uci import UCIAdapter


def test_uci_adapter_is_discoverable_via_entry_point() -> None:
    factories = discover_adapters()
    assert factories["uci"] is UCIAdapter


def test_uci_adapter_satisfies_protocol() -> None:
    assert isinstance(UCIAdapter(), Adapter)
