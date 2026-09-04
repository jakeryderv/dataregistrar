from pathlib import Path
from typing import Any

from dataregistrar.adapters import Adapter
from dataregistrar.cache import CachingAdapter, ResponseCache, cache_key
from dataregistrar.model import AccessPlan, Kind, Record


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class CountingAdapter:
    id = "fake"
    kinds = frozenset({Kind.DATASET})

    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str) -> list[Record]:
        self.calls.append(f"search:{query}")
        return [Record(id=f"fake:{query}", kind=Kind.DATASET, source="fake", name=query)]

    def get(self, source_id: str) -> Record:
        self.calls.append(f"get:{source_id}")
        return Record(id=f"fake:{source_id}", kind=Kind.DATASET, source="fake", name=source_id)

    def resolve(self, record: Record, selector: str | None = None) -> AccessPlan:
        raise NotImplementedError

    def retrieve(self, plan: AccessPlan, destination: Path) -> list[Path]:
        raise NotImplementedError


def test_put_get_expire_and_clear(tmp_path: Path) -> None:
    clock = Clock()
    cache = ResponseCache(tmp_path / "c.sqlite", clock=clock)
    key = cache_key("s", "search", "q")
    cache.put(key, source="s", op="search", arg="q", value="v", ttl=10)
    assert cache.get(key) == "v"
    clock.now += 11
    assert cache.get(key) is None
    assert cache.purge_expired() == 1
    cache.put(key, source="s", op="search", arg="q", value="v", ttl=10)
    cache.put(cache_key("t", "get", "1"), source="t", op="get", arg="1", value="w", ttl=10)
    assert cache.count() == 2
    assert cache.clear("s") == 1
    assert cache.count() == 1 and cache.count("t") == 1


def test_cache_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "c.sqlite"
    key = cache_key("s", "get", "1")
    ResponseCache(path).put(key, source="s", op="get", arg="1", value="v", ttl=60)
    assert ResponseCache(path).get(key) == "v"


def test_caching_adapter_serves_repeats_and_round_trips_records() -> None:
    clock = Clock()
    inner = CountingAdapter()
    cached = CachingAdapter(inner, ResponseCache(None, clock=clock), ttl=30)

    first = cached.search("wine")
    second = cached.search("wine")
    assert first == second
    assert inner.calls == ["search:wine"]

    assert cached.get("186") == cached.get("186")
    assert inner.calls == ["search:wine", "get:186"]

    clock.now += 31
    cached.search("wine")
    assert inner.calls == ["search:wine", "get:186", "search:wine"]
    assert cached.id == "fake" and cached.kinds == inner.kinds


def test_registry_wraps_adapters_and_fresh_bypasses(tmp_path: Path) -> None:
    from dataregistrar.registry import Layer, Registry

    (tmp_path / "sources.yaml").write_text(
        "sources:\n"
        "  - {id: fake, adapter: fake, cache_ttl: 60}\n"
        "  - {id: nocache, adapter: fake, cache_ttl: 0}\n"
    )
    inner = CountingAdapter()

    def factory(source_id: str, **_: Any) -> Adapter:
        return inner

    registry = Registry(
        [Layer("t", tmp_path)], factories={"fake": factory}, cache=ResponseCache(None)
    )
    assert isinstance(registry.adapter("fake"), CachingAdapter)
    assert registry.adapter("fake", fresh=True) is inner
    assert registry.adapter("nocache") is inner
    uncached = Registry([Layer("t", tmp_path)], factories={"fake": factory})
    assert uncached.adapter("fake") is inner
