# Architecture

Current state of the design. For why, see [`adr/`](adr/). For the product vision, see [`vision.md`](vision.md).

**Status:** UCI and Hugging Face adapters, overlays, policy engine, federated search, checksum-verified retrieval, CSV/parquet representations, and a per-source response cache are implemented. Tooling choices are in [ADR 0002](adr/0002-tooling-and-packaging-baseline.md). Project license is Apache-2.0.

## Modules

One responsibility each, matching the three layers in the vision.

| Module | Responsibility |
|---|---|
| `model` | Record, Kind, Status, License, Rights, AccessPlan. Pure data, no I/O. |
| `adapters` | The `Adapter` protocol, a base class with caching hooks, shipped adapters, entry-point discovery. |
| `registry` | Layer resolution (built-in → user/org → project), sources loader, overlay loader and merge. |
| `federated` | Fan-out to adapters, cache, normalize, merge overlays, rank. Named `federated` because `dataregistrar.search()` is the SDK function. |
| `policy` | SPDX license-to-rights table, rights derivation, presets, `DatasetPolicyError`. |
| `representations` | `LocalDataset`: retrieved files plus `as_pandas`, `as_arrow`, `as_numpy` behind lazy imports, and the attribution owed. |
| `download` | HTTP download with checksum verification. Leaf utility used by adapters. |
| `cache` | SQLite response cache and `CachingAdapter`, which wraps any adapter so search and get are served from the cache while fresh. TTL per source from `sources.yaml`; `fresh=True` bypasses. |
| `cli` | Typer app over all of the above, including the overlay create/verify workflow. |

Dependency direction is strictly downward:

```text
cli → federated → registry → adapters → model
              ↘ policy ↗        ↘ download ↗
```

Nothing imports upward. Adapters are testable without the registry; models without anything.

## Directory layout

```text
dataregistrar/
├── pyproject.toml
├── justfile
├── README.md  LICENSE
├── .github/workflows/
├── docs/
│   ├── vision.md
│   ├── architecture.md
│   ├── adr/
│   └── archive/
├── src/dataregistrar/
│   ├── __init__.py              exposes Registry, search, get
│   ├── model/
│   ├── adapters/
│   │   ├── __init__.py          protocol + registration
│   │   ├── huggingface.py       Hub HTTP API, no SDK; license tags → imported rights
│   │   ├── uci.py               API has no license field; rights stay unknown
│   │   └── release_series.py    (planned)
│   ├── registry/
│   │   ├── layers.py
│   │   ├── sources.py
│   │   └── overlays.py
│   ├── federated.py
│   ├── policy/
│   │   ├── engine.py
│   │   └── licenses.yaml        SPDX id → rights table
│   ├── cache.py                 response cache + CachingAdapter
│   ├── representations/
│   ├── cli/
│   └── builtin/                 the shipped layer
│       ├── sources.yaml
│       └── overlays/
└── tests/
    ├── unit/
    ├── contract/                one suite, parametrized over every adapter
    └── cassettes/
```

Placement decisions:

- Built-in sources and overlays live inside the package so they ship in the wheel. When community overlays outgrow the code they move to their own repo as a separately versioned package.
- JSON schemas are generated from the pydantic models, not hand-maintained.

## Runtime flow

```text
search(query, policy=…, min_status=…)
  → registry resolves enabled sources across layers
  → fan out to each adapter through CachingAdapter (cache hit or live call; --fresh bypasses)
  → adapters return normalized Records, status=imported
  → overlays merged: verified fields win, mirrors grouped under canonical id
  → policy engine derives rights from license table, applies preset
  → results with status, rights confidence, and evidence

retrieve(id, policy=…)
  → get, with policy enforced before any download
  → adapter.resolve → AccessPlan (one or more files)
  → overlay checksum attached to the plan, if one was recorded
  → adapter.retrieve into the user cache, verifying checksums, reusing verified files
  → LocalDataset: paths, attribution, as_pandas / as_arrow / as_numpy
```

## Layers

Sources and overlays resolve in order; later wins.

| Layer | Location | Contents |
|---|---|---|
| built-in | inside the package | shipped sources, community-verified overlays |
| user / org | `platformdirs` user config dir, or an org-managed git repo | private sources, org-verified overlays |
| project | `./dataregistrar/` in the working tree | project-specific sources and overlays |

Every overlay records which layer it came from, so `verified` means verified by a named reviewer in a named layer.

## Next steps

1. Overlay CLI: create from a record, run the verification checklist, mark verified.
2. `release-series` adapter and one government source.
