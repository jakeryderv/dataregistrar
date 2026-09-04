# dataregistrar — Vision

A provider-agnostic catalog and access layer for public data. One interface to discover, evaluate, retrieve, and load data from many sources, with licensing, provenance, and source metadata preserved and inspectable.

## 1. Motivation

Finding data is easy. Finding data you are actually allowed to use for a given purpose, from a source you can cite, in a form you can load, is not. Provider catalogs disagree about licensing, mirrors and conversions appear as unrelated datasets, and "publicly available" is routinely mistaken for "openly licensed." Engineers hand-check license pages, or don't.

This is a general-purpose tool. It does not target one domain or one workflow. It gives one consistent way to find data of any kind, see what is known about its licensing and provenance and how confidently, and then download and load it, whatever you intend to do with it afterward.

Because it is general, scope is checked against representative questions rather than one project. The tool is doing its job when it answers these well:

- "Tabular datasets about X that I can use commercially, with the license evidence and a citation."
- "Load this dataset into a dataframe, and tell me what attribution I owe."
- "Is this Kaggle dataset the same as the NOAA original, and which one should I cite?"
- "What am I allowed to do with this specific dataset, and how sure is that answer?"
- "The latest release of this government series, and whether last year's was re-issued."

If a proposed feature does not make one of these answers better, it waits.

## 2. Concept

The project defines a common contract for describing and accessing data, plus three thin layers built on it: **adapters** that wrap sources, a **registry** that says which sources are in play, and **overlays** that carry human-verified facts. The system knows where data lives, how to retrieve it, what form it takes, and what a user is permitted to do with it.

**The product is the contract and the three layers together, and every layer is user-extensible.** The package ships defaults for each: hub adapters, a default source list, community-verified overlays. Nothing in the design privileges those defaults. A user's own adapter for an internal data lake, a team's private source list, or a company's legal-reviewed overlays get the same search, policy, and confidence treatment as the shipped ones, in the same query.

**Everything is an adapter.** A hub like Hugging Face is an adapter with a large catalog behind a search API. A quarterly government file is an adapter with a catalog of one. A market-data API is an adapter whose catalog is tickers. The SDK federates search across whichever adapters are configured, normalizes every result into one record shape, and layers human-reviewed facts on top where they exist.

```text
                      dataregistrar SDK
                             │
             ┌───────────────┼────────────────┐
             │               │                │
        Federated        Overlay           Policy
         search          registry          engine
             │               │                │
             └───────────────┼────────────────┘
                             │
                      Adapter protocol
                             │
     ┌────────┬───────┬──────┼──────┬───────────┬────────────────┐
    HF       UCI   OpenML  Kaggle  yfinance    gov release      …
  (hub)     (hub)   (hub)   (hub)  (query-api) (release-series)
```

### Federated catalog, sparse overlay

The earlier draft made a hand-curated registry the center of the system. That does not scale to hubs with hundreds of thousands of entries, and it is not where the value is. The design is now:

- **Adapters decide what exists.** They turn a source's native search and retrieval into one contract. A dataset is "registered" by virtue of its source having an adapter. Nobody writes an entry per hub dataset.
- **The registry decides which sources are in play.** It is a short list of enabled adapters plus config for one-off sources. It is never a gate on what appears.
- **Overlays decide what has been checked.** An overlay is an optional note on a single record carrying facts a human has reviewed: a verified license, a citation the hub lacks, a link from a mirror to its canonical source. Overlays are sparse by design. A record with no overlay still appears in search; it just carries lower confidence.
- **Confidence is visible on every result.** Hub metadata is normalized but unreviewed, so it is `imported`. An overlay that has passed the verification checklist is `verified`. Search never lets the two look alike.

```text
Hub / API / file sources
      ↓
Adapters → normalized records (cached)          ← overlays (git, sparse)
      ↓                                                ↓
Federated search → merge → policy filter → result with confidence + evidence
      ↓
Selected distribution → adapter retrieval → representation
```

```python
registry.search("storm events")                       # all configured sources
registry.search("storm events", sources=["uci"])      # narrow the fan-out
registry.search("storm events", min_status="verified")
registry.get("hf:org/dataset")                        # provider-scoped id
registry.get("noaa-storm-events")                     # canonical id, via overlay
```

**Curation is where trust comes from.** Hub license tags are unreliable everywhere. A rights claim is only trustworthy because a person checked it against evidence. Overlays are the mechanism; how fast they can be produced is a project metric.

## 3. Non-goals

- **No hosting or mirroring of data contents** in v1. Retrieval is source-native. Caching comes only after the rights model is proven and only where terms explicitly permit it.
- **No legal advice.** The policy engine provides decision support with traceable evidence. Custom licenses, data-use agreements, privacy constraints, and commercial deployment still require human review.
- **No hand-written record per hub dataset.** Ever. If it feels like that is needed, the adapter is missing a normalization step.
- **No Kaggle adapter in v1.** Credentials, competition rules, and scraping-unfriendly terms make it the worst first hub. Phase 2.
- **No `stream` implementation in v1.** The kind is modeled so nothing blocks it, but a streaming SDK surface is a separate design.
- **No non-tabular representations, REST API, authentication, or multi-tenant governance in v1.**

## 4. Prior art and what is different

- **Croissant** (MLCommons): JSON-LD metadata for ML datasets, adopted by Hugging Face, Kaggle, OpenML, and TensorFlow Datasets. Covers identity, license, distributions, record schemas. The `dataset` kind borrows its vocabulary.
- **schema.org Dataset / DataDownload**: underlies Google Dataset Search; maps onto the canonical-vs-distribution model.
- **intake**: a catalog-of-sources library with plugins for files, databases, and APIs. The closest prior art for "everything is an adapter." It does not model rights, confidence, or cross-source identity.
- **Hugging Face Hub, OpenML, `ucimlrepo`, `sklearn.datasets.fetch_openml`**: single-provider catalogs and loaders.

What none of them do, and what this project is for:

1. **Federated search over many kinds of source** behind one record shape and one access contract.
2. **Evidence-backed rights filtering**, where every claim carries its source and verification date and unknown is treated as unknown.
3. **Visible confidence on every result**, so unreviewed hub metadata is never mistaken for reviewed metadata.
4. **Cross-source canonicalization**, sparse and opt-in, so an official source, a Kaggle mirror, and a Hugging Face conversion can be grouped once someone has confirmed they are the same thing.
5. **User-owned layers.** Private sources and org-specific verified claims sit alongside public ones in one search, with the same contract.

Reuse existing vocabularies where they fit. Invent only the rights, confidence, and cross-source extensions that do not exist yet.

## 5. Core design

### 5.1 Sources and adapters

A source is a configured adapter instance. Hubs need no configuration beyond enabling them. One-off sources carry their own config.

```yaml
# registry/sources.yaml
sources:
  - id: huggingface
    adapter: dataregistrar.adapters.huggingface
    kinds: [dataset]

  - id: uci
    adapter: dataregistrar.adapters.uci
    kinds: [dataset]

  - id: noaa                          # one publisher, many delivery mechanisms
    adapter: dataregistrar.adapters.noaa
    kinds: [dataset, release-series]

  - id: yfinance                      # later; shown to prove the model does not block it
    adapter: dataregistrar.adapters.yfinance
    kinds: [query-api]
```

The adapter contract:

```python
class Adapter(Protocol):
    kinds: frozenset[Kind]

    def search(self, query: str, **filters) -> list[Record]: ...
    def get(self, source_id: str) -> Record: ...
    def resolve(self, record: Record, selector: Selector | None = None) -> AccessPlan: ...
    def retrieve(self, plan: AccessPlan, destination: Path | None = None) -> Path: ...
```

`search` and `get` return normalized records with status `imported`. Responses are cached with a per-source TTL so repeat searches do not fan out. Native libraries and HTTP APIs are replaceable details behind the contract, and provider-native access stays available for advanced use.

**v1 adapters: Hugging Face and UCI as hubs, plus NOAA as a publisher adapter** to prove the non-hub path. A publisher adapter is a composite: an organization-level catalog for discovery, plus *collections*, each of which knows one delivery mechanism and is the only way to retrieve. Catalog entries with no collection are metadata-only, and `resolve` says so. Storm Events is NOAA's first collection, a `release-series` over a plain file directory. Adding the next NOAA collection is one file; the same shape will fit BLS, Census, and NASA. Hugging Face because it is the largest general catalog and its gating and license tags exercise the rights model. UCI because it is tabular-heavy, mostly CC-BY-4.0, and cheap to verify. OpenML is the first phase-2 hub; Kaggle follows.

### 5.2 Record model

Every record, whether produced live by an adapter or stored as an overlay, has the same core fields and a `kind`.

```yaml
id: hf:org/some-dataset              # provider-scoped; canonical ids come from overlays
kind: dataset                        # dataset | release-series | query-api | stream
source: huggingface
name: Some Dataset
description: "..."
url: https://huggingface.co/datasets/org/some-dataset
publisher: org
citeAs: null

license:
  spdx: CC-BY-NC-4.0
  evidence_url: https://huggingface.co/datasets/org/some-dataset   # the hub tag
  verified_at: null
  verified_by: null

rights:                              # derived from the license table
  commercial_use: false
  redistribution: true
  derivatives: true
  model_training: unknown
  attribution_required: true
  share_alike: false
  confidence: imported

access:
  authentication: false
  gated: true

data:
  modality: tabular
  tasks: [classification]

status: imported
```

Kind-specific fields live in an `access` sub-block whose shape depends on `kind` (see 5.7). Rights claims always carry their source and verification date. Unknown or ambiguous rights remain `unknown`; the platform never infers permission from availability.

### 5.3 Overlays and identifiers

Provider-scoped ids (`hf:org/name`, `uci:186`, `noaa-storm-events:2024`) are the default and need no registry entry. A **canonical id** exists only when an overlay creates one. Overlays are the sparse, human-reviewed layer.

```yaml
# registry/overlays/noaa-storm-events.yaml
canonical: noaa-storm-events
kind: release-series
name: NOAA Storm Events Database
publisher: NOAA National Centers for Environmental Information
citeAs: "NOAA NCEI, Storm Events Database, ..."

distributions:
  - id: noaa-storm-events            # the configured release-series source
    role: official
  - id: kaggle:someone/noaa-storm-events
    role: mirror
    modifications: "single CSV, 1950-2022 only"
  - id: hf:org/storm-events
    role: conversion
    modifications: "parquet, columns renamed"

license:
  spdx: US-Government-Works          # placeholder; confirm exact SPDX id
  evidence_url: https://www.ncei.noaa.gov/.../terms
  verified_at: 2026-09-01
  verified_by: jake

rights:
  commercial_use: true
  redistribution: true
  derivatives: true
  model_training: true
  attribution_required: false
  share_alike: false
  confidence: verified

status: verified
```

At search time, overlays are merged over adapter results: verified fields win, and provider ids listed as distributions are grouped under the canonical id so a NOAA dataset with a Kaggle mirror appears once.

Canonicalization is evidence-based and reversible. When two records cannot be confidently matched they stay separate, with a `possible_duplicate_of` hint rather than a forced merge.

**Decision: sources and overlays live as files in git, validated in CI.** They are small, they are the human-reviewed layer, and git gives history, diffs, and review for free. Adapter results are never written to git; they are cached locally with a TTL. Overlays are written by the CLI, not by hand.

### 5.4 Status and verification

- `discovered`: returned by a source but normalization was partial or failed;
- `imported`: normalized by an adapter, source metadata preserved, nothing reviewed;
- `verified`: an overlay exists and every check below is recorded;
- `stale`: upstream differs from what the overlay recorded, or verification is older than the configured window;
- `restricted`: known access or policy requirements apply, at any confidence level.

**An overlay is `verified` only when all of the following are recorded:**

1. license text or statement located at an official URL, captured as evidence;
2. official source URL resolves and is confirmed as the publisher's own;
3. for `dataset` and `release-series`, at least one distribution has a checksum;
4. retrieval through the adapter succeeded end to end;
5. a citation is present;
6. a named reviewer and date.

Anything less is `imported`. Verification identifies what was checked, not a legal guarantee.

### 5.5 Versioning and staleness

- `dataset`: version is the provider's where one exists, else the capture date, with a checksum.
- `release-series`: each release has an id, a date, and a checksum; the series records cadence and revision policy. `latest` resolves to the newest release, and re-issued prior releases are new releases with a `supersedes` link, never silent replacements.
- `query-api` and `stream`: no artifact version. Provenance is the query or subscription parameters plus the time of access.
- A scheduled refresh re-runs `get` for every overlaid record. Any change in license, checksum, or access requirements **opens a reviewable diff** against the overlay and marks it `stale`. Verified fields are never overwritten automatically.

### 5.6 Licensing and policy engine

Licensing is a first-class capability, not a metadata field.

**Decision: the license-to-rights mapping is a versioned data table keyed by SPDX identifier**, shipped with the package and reviewed like any other record. Adapters map a source's native license field to an SPDX id where they can; the derived `rights` block carries `confidence: imported`. An overlay may override any right with its own evidence, raising confidence to `verified`. Licenses with no SPDX id, terms-of-service, and custom agreements map to `unknown` for every right until reviewed.

Rights evaluated separately:

- commercial use;
- redistribution and mirroring;
- modification and derived datasets;
- model training and model publication;
- attribution and share-alike obligations;
- research-only, competition-only, or other custom terms;
- credential, registration, or data-use-agreement requirements.

Policy presets (`open`, `permissive`, `commercial`, `redistributable`, `research`, `any`) are documented, versioned rules over those rights.

```python
results = registry.search(
    "human activity recognition",
    modality="tabular",
    policy="commercial",           # filters on rights at any confidence, flags imported ones
)

results = registry.search(
    "human activity recognition",
    policy="commercial",
    min_status="verified",         # only overlay-backed claims
)

dataset = registry.get(
    "uci:186",
    require={"commercial_use": True, "derivatives": True},
)
```

An incompatible request fails clearly and cites its evidence:

```text
DatasetPolicyError

Record:           hf:org/some-dataset
Declared license: CC-BY-NC-4.0 (evidence: hub tag at https://…, confidence: imported)
Requested:        commercial_use=True
Reason:           commercial use is not permitted by the declared license.
```

For `query-api` and `stream` kinds the rights basis is a terms-of-service rather than a license. The same rights vocabulary applies, but adapters must not guess: those records start with every right `unknown` and require an overlay to say otherwise.

### 5.7 Kinds

`kind` is on every record from day one so later source types need no schema change. Only the first two are implemented in v1.

| kind | what it is | access surface | version / provenance | rights basis | v1 |
|---|---|---|---|---|---|
| `dataset` | fixed artifact(s) | `files()`, `as_pandas()`, … | provider version + checksum | license | implemented |
| `release-series` | recurring artifacts on a cadence | `releases()`, `latest()`, `load(release)` | release id, date, checksum, cadence, revision policy | license | implemented, one source |
| `query-api` | parameterized endpoint | `query(**params)` | parameters + access time | terms of service | modeled; optional proof-of-concept |
| `stream` | continuous feed | `subscribe()` | subscription params + time | terms of service | modeled only |

Each kind owns the shape of its `access` block and its `AccessPlan`. The search, policy, overlay, and status machinery is kind-agnostic.

### 5.8 Extensibility and layering

Every layer has a "yours" slot next to the "ours" one.

**Adapters.** Installed plugins are discovered through Python entry points. One-off adapters can also be registered at runtime:

```python
registry.adapters.register("lakehouse", LakehouseAdapter(conn))
```

**Sources and overlays resolve in layers.** Later layers win, following the same pattern as git or pip configuration:

```text
1. package built-ins        shipped defaults, community-verified overlays
2. user / org layer         ~/.config/dataregistrar/  or an org-managed git repo
3. project layer            ./dataregistrar/  in the working tree
```

A layer is just a directory containing `sources.yaml` and `overlays/`. A team shares theirs through their own git repo. Community overlays can move to a separate repo from the code once they outgrow it.

**Overlay provenance is per layer.** Every overlay records which layer it came from, so `verified` always means verified by a named reviewer in a named layer. This matters because rights depend on who is asking: what is commercially safe for one organization under its counsel's reading is not automatically safe for another. An org-level overlay stating "legal reviewed this on this date" is a fact only that org can assert, and it is the kind of fact no hub can offer.

**What extension does not change.** Adapters still decide what exists, overlays still decide what has been checked, and the registry still is not a gate. User-defined pieces obey the same contract, the same status states, and the same verification checklist as shipped ones.

## 6. Retrieval and representations

Source-native retrieval is the default:

```text
User → SDK → resolve(record, selector) → AccessPlan → adapter → user
```

The platform returns normalized metadata and invokes the source's supported access path without storing the data. Optional caching or mirroring is a later phase, permitted only where recorded terms explicitly allow it, and must retain license, attribution, source, version, checksums, and update history.

Representations are offered only where they make sense for the kind and modality. **v1 is tabular only:**

```python
record.metadata
record.license
record.citation
record.provenance

# dataset
ds.files()
ds.as_pandas()
ds.as_arrow()
ds.as_numpy()

# release-series
series.releases()
series.latest().as_pandas()
series.load("2024").files()
```

Raw files and provider-native access remain available so normalization never hides structure or silently changes data. Later modalities add `as_xarray()`, `as_geopandas()`, `as_huggingface()`, and others.

## 7. v1

The first release proves that federated search plus a sparse verified overlay is useful, without becoming a hosting operation or a curation backlog.

### Scope

1. Record model with `kind`, status states, adapter protocol, `sources.yaml`, overlay schema. Confirm Croissant alignment for the `dataset` kind.
2. Hugging Face and UCI hub adapters with federated search and a local response cache.
3. One `release-series` adapter and one configured source to prove the non-hub path.
4. License table keyed by SPDX id; `commercial`, `permissive`, and `redistributable` policy filters; `min_status` filtering.
5. Overlay CLI: create an overlay from a record, run the verification checklist, mark verified. Overlays for whatever the driving use case needs.
6. Tabular representations: raw files, pandas, Arrow, NumPy.
7. Layered resolution of sources and overlays (built-in, user, project) and entry-point adapter discovery.
8. CI validation of sources and overlays. Deterministic tests with recorded adapter fixtures; tests never hit live sources and never mirror data.

### Success criteria

| Criterion | Target |
|---|---|
| Hub adapters passing the contract test suite | 2 |
| Non-hub sources working end to end | 1 |
| Policy filters with documented rules | 3 |
| Verified overlays | enough for the section 1 use case, minimum 10 |
| Real projects using `search(policy=…)` end to end | 1 |
| Time to produce a verified overlay | measured, so phase 2 can plan curation |

## 8. Roadmap

- **Phase 1 — Federated search, rights, and overlays.** v1 above.
- **Phase 2 — More hubs and kinds.** OpenML, Kaggle, Zenodo, Figshare. More `release-series` sources for government data. First `query-api` adapter. First non-tabular modality.
- **Phase 3 — Provenance and canonicalization.** Automated duplicate candidates across sources, lineage, scheduled re-verification, version comparison.
- **Phase 4 — Hosted API and governed caching.** REST mirroring the SDK, authentication, quotas, team policy profiles, audit records, opt-in caching only for redistributable data.
- **Phase 5 — Streams.** A streaming SDK surface, once the rest is stable.
- **Beyond.** See appendix.

## 9. Guiding principles

- The product is the contract and its layers, all user-extensible. The registry is never a gate.
- Everything is an adapter, and shipped defaults get no special treatment.
- Index broadly, but grant access conservatively.
- Every result carries its confidence. Imported must never look verified.
- Treat missing or unclear rights as unknown, not permissive.
- Prefer official sources and source-native retrieval.
- Cache or mirror only with explicit permission and preserved obligations.
- Keep provenance, policy evidence, and versions inspectable.
- Standardize access without erasing kind- or modality-specific structure.
- Make every policy decision explainable and overrideable only through explicit configuration.
- Curation throughput is a product metric.

## Appendix: long-term shape

None of this shapes v1.

**Creation and publishing.** The same interface can eventually cover first-party data hosted by the platform, curated aggregations derived reproducibly from registered sources, user-created datasets, and publishing to hubs while retaining one canonical identity. Curated releases would record exact inputs, transformation recipe, license compatibility, provenance, version, and validation results.

**Positioning.** If this becomes a product, the product is data infrastructure, not a resale catalog. Value lies in the trustworthy access and policy system around the data, never in claiming ownership of the data itself. Each source remains governed by its own license, terms, and provider.

## Open decisions

- **Croissant alignment.** Confirm during v1 item 1 whether `dataset` records are Croissant JSON-LD with an extension, or a YAML schema that exports to Croissant.
- **First `release-series` source.** Pick one real government dataset with an awkward cadence. NOAA Storm Events is the placeholder.
- **Cache location and TTL policy.** Per-source TTL defaults, and whether the cache is SQLite or files.
