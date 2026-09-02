# Architecture

Current state of the design. For why, see [`adr/`](adr/). For the product vision, see [`vision.md`](vision.md).

**Status:** accepted, no code yet. Tooling choices are in [ADR 0002](adr/0002-tooling-and-packaging-baseline.md). Project license is Apache-2.0.

## Modules

One responsibility each, matching the three layers in the vision.

| Module | Responsibility |
|---|---|
| `model` | Record, Kind, Status, License, Rights, AccessPlan. Pure data, no I/O. |
| `adapters` | The `Adapter` protocol, a base class with caching hooks, shipped adapters, entry-point discovery. |
| `registry` | Layer resolution (built-in → user/org → project), sources loader, overlay loader and merge. |
| `search` | Fan-out to adapters, cache, normalize, merge overlays, rank. |
| `policy` | SPDX license-to-rights table, rights derivation, presets, `DatasetPolicyError`. |
| `representations` | `as_pandas`, `as_arrow`, `as_numpy` behind lazy imports. |
| `cli` | Typer app over all of the above, including the overlay create/verify workflow. |

Dependency direction is strictly downward:

```text
cli → search → registry → adapters → model
              ↘ policy ↗
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
│   │   ├── huggingface.py
│   │   ├── uci.py
│   │   └── release_series.py
│   ├── registry/
│   │   ├── layers.py
│   │   ├── sources.py
│   │   └── overlays.py
│   ├── search.py
│   ├── policy/
│   │   ├── engine.py
│   │   └── licenses.yaml        SPDX id → rights table
│   ├── cache.py
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
  → fan out to each adapter (cache hit or live call)
  → adapters return normalized Records, status=imported
  → overlays merged: verified fields win, mirrors grouped under canonical id
  → policy engine derives rights from license table, applies preset
  → results with status, rights confidence, and evidence

get(id) → resolve(record, selector) → AccessPlan → adapter.retrieve → representation
```

## Layers

Sources and overlays resolve in order; later wins.

| Layer | Location | Contents |
|---|---|---|
| built-in | inside the package | shipped sources, community-verified overlays |
| user / org | `platformdirs` user config dir, or an org-managed git repo | private sources, org-verified overlays |
| project | `./dataregistrar/` in the working tree | project-specific sources and overlays |

Every overlay records which layer it came from, so `verified` means verified by a named reviewer in a named layer.

## Next step

Walking skeleton: one adapter, one record, one search, one policy check, end to end with a recorded cassette.
