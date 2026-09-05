# Architecture

Current state of the design. For why, see [`adr/`](adr/). For the product vision, see [`vision.md`](vision.md).

**Status:** UCI and Hugging Face adapters, overlays, policy engine, federated search, checksum-verified retrieval, CSV/parquet representations, a per-source response cache, the overlay create/verify workflow, and the NOAA publisher adapter with its Storm Events release series are implemented. Tooling choices are in [ADR 0002](adr/0002-tooling-and-packaging-baseline.md). Project license is Apache-2.0.

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
| `curate` | Create an overlay from a live record; run the verification checklist and write it back as verified only on a full pass. |
| `cli` | Typer app over all of the above. |

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
│   │   └── noaa/                publisher adapter: NCEI catalog + collections
│   │       ├── catalog.py       NCEI search service, metadata-only records
│   │       ├── series.py        directory-listing → releases helper
│   │       └── collections/     one delivery mechanism each; storm_events.py first
│   ├── registry/
│   │   ├── layers.py
│   │   ├── sources.py
│   │   └── overlays.py
│   ├── federated.py
│   ├── policy/
│   │   ├── engine.py
│   │   └── licenses.yaml        SPDX id → rights table
│   ├── cache.py                 response cache + CachingAdapter
│   ├── curate.py                overlay create / verify
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

## Publisher adapters

A hub adapter wraps one API. A publisher like NOAA has one identity and a dozen delivery mechanisms, so its adapter is a composite:

- **Catalog** for `search` and `get`: NCEI's search service today; OneStop and data.gov can feed the same adapter later. Catalog records are `imported`, rights unknown, and `access.retrievable = False`.
- **Collections** for retrieval: each knows one delivery mechanism, contributes its own catalog entry so it is searchable even when the publisher's catalog omits it, and implements `resolve` for its kind. `DirectorySeries` is a base for the common case, a file directory with one file per period; a new collection of that shape is a class with nine attributes (GHCN-Daily is the second). A collection that takes the catalog's id for the same dataset merges with the catalog hit. Storm Events is a `release-series` over a file directory: filenames encode period and revision, planned filenames are `<period>/<name>` so re-issues never overwrite, and `resolve(record, selector)` picks a release, default latest.
- **Overlay status flows only to distributions that were checked.** The official distribution and any distribution with recorded checksums take the overlay's status; a linked mirror that has never been retrieved keeps its own status while still gaining the canonical id and license.
- **Re-issue detection** happens where overlays meet series: a recorded checksum key with the same period but a different filename marks the release `supersedes` and a verified record `stale`.

The public adapter protocol does not change; collections are internal to the adapter.

## Next steps

1. Scheduled refresh: re-run `get` for every overlaid record and report which went stale.
2. OneStop and data.gov as additional NOAA catalogs.
3. First `query-api` collection, probably NOAA CO-OPS tides, to exercise the third kind.
