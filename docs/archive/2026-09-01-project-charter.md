> **Archived 2026-09-01.** Superseded by [vision.md](../vision.md). Kept for comparison; the registry-first model described here was replaced by the federated catalog with sparse overlays (see [ADR 0001](../adr/0001-federated-catalog-with-sparse-overlays.md)).

# Dataset Registry & Unified Access Layer

## Concept

A provider-agnostic dataset registry and access layer that gives applications and machine-learning workflows one interface for discovering, evaluating, retrieving, and loading public datasets while preserving licensing, provenance, and source metadata.

The project is more than a wrapper around Kaggle, UCI, or Hugging Face. It defines a common protocol over heterogeneous providers: the system knows where a dataset lives, how to retrieve it, what form it takes, and what a user is permitted to do with it.

```text
                       Dataset Platform
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
      Registry            Policy              Access
    and discovery         engine              layer
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                      Provider adapters
                              │
       ┌────────┬──────┬──────┼───────┬────────┬───────┐
     Kaggle    UCI     HF   OpenML  Zenodo  Figshare  NOAA/NASA …
```

The registry can describe all datasets for which it has reliable metadata. Policy views then expose open, permissive, commercial-safe, redistributable, research-only, or unrestricted subsets. “Publicly available” must never be treated as equivalent to “openly licensed.”

## Registry-Centered Hybrid

The registry is the product; adapters are supporting infrastructure for discovering, synchronizing, and retrieving datasets. This avoids the weaknesses of both extremes:

- An adapter-only meta-search offers broad coverage quickly, but results are slow, inconsistent, duplicated, dependent on provider availability, and difficult to filter reliably by policy.
- A purely manual registry offers consistent and trustworthy records, but grows slowly and becomes expensive to keep current.
- A registry-centered hybrid uses adapters to expand and refresh coverage while keeping normal search fast, canonical, and policy-aware.

```text
Provider catalogs
      ↓
Provider adapters → discovered candidates
      ↓
normalize → deduplicate → verify
      ↓
Canonical registry ← first-party and user-created datasets
      ↓
Registry search → selected distribution → adapter retrieval
```

Normal `search()` queries the registry. A separate `discover()` operation can search live provider catalogs for datasets that have not yet been registered. This distinction prevents incomplete provider results from appearing as trustworthy as reviewed registry entries.

```python
datasets.search("storm events")       # Canonical registry records
datasets.discover("storm events")     # Live provider candidates
datasets.register("hf:org/dataset")   # Import a candidate for normalization
```

Records should expose their level of confidence rather than imply that every imported claim has been reviewed:

- `discovered`: returned by a provider but not normalized;
- `imported`: normalized automatically with source metadata preserved;
- `verified`: defined checks completed against authoritative evidence;
- `stale`: upstream information changed or verification is too old;
- `restricted`: known access or policy requirements apply.

Verification should identify what was checked—such as the official metadata source, license evidence, provenance, checksums, and retrieval—not imply a legal guarantee. Provider changes should create reviewable updates rather than silently replacing verified claims.

### Future Expansion: Dataset Creation and Publishing

The same interface can eventually support datasets regardless of where they originate or live:

- third-party datasets retrieved from providers such as UCI, Kaggle, or Hugging Face;
- first-party datasets created and hosted by the platform;
- curated aggregations derived reproducibly from multiple registered sources;
- datasets published to Kaggle, Hugging Face, or other providers while retaining one canonical registry identity;
- user-created datasets registered, hosted, or published through the service.

A canonical dataset remains distinct from its distributions. One dataset may have a first-party hosted release, a Kaggle distribution, and a Hugging Face distribution without appearing as three unrelated datasets. Curated releases should record their exact inputs, transformation recipe, license compatibility, provenance, version, and validation results.

## Core Architecture

### 1. Canonical Dataset Registry

Each dataset receives a stable identifier and normalized metadata record while retaining the provider's original metadata. A record should cover:

- identity, description, version, and provider identifiers;
- official source, mirrors, publisher, citation, and lineage;
- declared license and data-use agreement;
- permitted uses, restrictions, attribution, and access requirements;
- modality, tasks, formats, schema, size, features, and target information;
- retrieval method, authentication, gating, and update status;
- hosting, caching, and mirroring permissions.

```yaml
id: uci/wine-quality
name: Wine Quality
version: "latest"

source:
  provider: uci
  provider_id: 186
  url: https://example.org/datasets/186
  official: true

license:
  id: CC-BY-4.0
  source_url: https://example.org/license
  verified_at: 2026-09-01
  commercial_use: true
  redistribution: true
  derivatives: true
  model_training: true
  attribution_required: true

access:
  authentication: false
  gated: false

hosting:
  cacheable: true
  mirrorable: true

data:
  modality: tabular
  tasks: [regression, classification]
  formats: [csv]
  target: quality

provenance:
  publisher: "..."
  citation: "..."
  canonical_dataset: uci/wine-quality
```

License claims should carry their source and verification date. Unknown or ambiguous rights remain `unknown`; the platform must not infer permission from availability or silently convert missing metadata into approval.

### 2. Provider Adapters

Adapters translate provider-specific catalogs and retrieval libraries into one internal contract. Native libraries and HTTP APIs are replaceable implementation details behind that contract.

```python
class ProviderAdapter:
    def discover(self, query, **filters): ...
    def inspect(self, provider_id): ...
    def resolve(self, dataset_id, version=None): ...
    def retrieve(self, distribution, destination=None): ...
```

Initial adapters should cover Kaggle, UCI, Hugging Face, and OpenML. Later adapters can add Zenodo, Figshare, NOAA/NCEI, NASA Earthdata, Data.gov, AWS Registry of Open Data, Google Cloud Public Datasets, PhysioNet, OpenStreetMap, Common Crawl, and other domain repositories.

Provider-specific access remains available for advanced use, but the normal path should not require users to know where a dataset is hosted.

### 3. Licensing and Policy Engine

Licensing is a first-class capability, not merely a metadata field. The engine evaluates separate rights and constraints such as:

- commercial use;
- redistribution and mirroring;
- modification and derived datasets;
- model training and publication;
- attribution and share-alike obligations;
- research-only, competition-only, or other custom terms;
- credential, registration, or data-use-agreement requirements.

Useful policy presets include `open`, `permissive`, `commercial`, `redistributable`, `research`, and `any`. Presets should be documented, versioned rules rather than claims of universal legal certainty.

```python
results = datasets.search(
    "human activity recognition",
    modality="timeseries",
    policy="commercial",
)

dataset = datasets.get(
    "provider/dataset",
    require={
        "commercial_use": True,
        "derivatives": True,
        "redistribution": True,
    },
)
```

An incompatible request fails clearly:

```text
DatasetPolicyError

Dataset license: CC-BY-NC-4.0
Requested policy: commercial_use=True
Reason: commercial use is not permitted by the declared license.
```

The engine provides decision support and traceable evidence, not legal advice. Custom licenses, provider terms, privacy constraints, and commercial deployment still require appropriate review.

## Retrieval, Caching, and Provenance

Source-native retrieval is the default:

```text
User → unified SDK/API → resolved official provider → user
```

The platform returns normalized metadata and invokes the source provider's supported access path without storing the dataset itself. This keeps data current and avoids assuming redistribution rights.

Optional caching or mirroring can be added only when the recorded terms explicitly allow it. A cache must retain the applicable license, attribution, source, version, checksums, and update history. Full hosting should come later, because it introduces responsibility for redistribution, takedowns, privacy, storage, bandwidth, versioning, and ongoing license compliance.

Provenance prevents mirrors and conversions from appearing as unrelated datasets. For example:

```text
Canonical NOAA dataset
├── official NOAA source
├── Kaggle mirror
├── Hugging Face conversion
└── OpenML version
```

Search results should group these records around a canonical dataset while exposing each distribution's provider, format, version, modifications, and license evidence. Canonicalization should be evidence-based and reversible when two records cannot be confidently matched.

## Standardized Dataset Representations

The platform should normalize interfaces without forcing every dataset into a universal `X, y` shape. A dataset declares a modality such as `tabular`, `image`, `text`, `audio`, `video`, `timeseries`, `geospatial`, `graph`, or `multimodal`.

Representations are offered only where they make sense:

```python
dataset.metadata
dataset.schema
dataset.license
dataset.citation
dataset.provenance
dataset.versions

dataset.as_pandas()
dataset.as_numpy()
dataset.as_arrow()
dataset.as_xarray()
dataset.as_geopandas()
dataset.as_huggingface()
```

Provider-native access and raw files remain available so normalization never hides meaningful structure or silently changes the data.

## Product Interfaces

Build the Python SDK first and expose the same core through a REST API.

```python
import dataset_registry as datasets

results = datasets.search(
    "wearable human activity recognition",
    modality="timeseries",
    commercial_use=True,
)

# Optional live discovery outside the verified registry
candidates = datasets.discover(
    "wearable human activity recognition",
    providers=["kaggle", "huggingface"],
)

dataset = results[0]
print(dataset.license)
print(dataset.schema)
print(dataset.citation)

data = dataset.load()

# Explicit provider access when needed
datasets.kaggle.get("owner/dataset")
datasets.uci.get(186)
datasets.huggingface.get("namespace/dataset")
```

```http
GET /v1/datasets?query=weather&policy=commercial&modality=timeseries
GET /v1/discover?query=weather&provider=noaa
GET /v1/datasets/noaa/storm-events
GET /v1/datasets/noaa/storm-events/versions
POST /v1/datasets/noaa/storm-events/resolve
POST /v1/registrations
```

The REST response should include the policy decision, evidence used, obligations such as attribution, provenance, and either a source-native retrieval plan or a permitted cached artifact.

## MVP

The first release should prove that the abstraction is useful without becoming a large hosting operation:

1. Define the canonical metadata, verification states, and provider-adapter contracts.
2. Implement Python SDK adapters for UCI, Hugging Face, Kaggle, and OpenML.
3. Add registry-first search, stable identifiers, dataset details, and source-native retrieval.
4. Normalize declared licenses and implement conservative commercial, permissive, and redistributable filters.
5. Support tabular datasets with raw-file, pandas, NumPy, and Arrow representations.
6. Preserve citations, attribution requirements, provider URLs, and basic provenance.
7. Import a small curated catalog and distinguish automatically imported records from verified ones.
8. Add deterministic tests without mirroring dataset contents.

## Phased Roadmap

### Phase 1 — Unified discovery and retrieval

Ship the Python SDK, registry-first search, core registry, four initial adapters, verification states, license evidence, basic policy filters, and tabular representations.

### Phase 2 — Broader providers and modalities

Add Zenodo, Figshare, NOAA, NASA, and other domain adapters; introduce text, image, time-series, and geospatial representations; improve schema and version metadata.

### Phase 3 — Provenance and canonicalization

Link official sources, mirrors, conversions, and forks; add checksums, lineage, duplicate detection, citations, and version comparison.

### Phase 4 — Hosted API and governed caching

Expose the REST API, authentication, quotas, team policy profiles, audit records, and opt-in caching only for datasets whose terms permit redistribution.

### Phase 5 — Dataset infrastructure platform

Add semantic discovery, organization-specific governance, reproducible retrieval manifests, transformations, first-party and user-created datasets, multi-provider publishing, observability, enterprise integrations, and carefully scoped hosting.

## Commercial Positioning

The commercial product is **dataset infrastructure**, not a resale catalog of datasets. Customers pay for unified discovery, metadata quality, policy evaluation, provenance, reliable access, transformations, caching, governance, and auditability.

This positioning supports a hosted service while respecting that each dataset remains governed by its own license, data-use agreement, original source, and provider terms. The defensible value lies in the trustworthy registry and access system around the data—not in claiming ownership of the data itself.

## Guiding Principles

- Index broadly, but grant access conservatively.
- Keep registry search distinct from live provider discovery.
- Treat missing or unclear rights as unknown, not permissive.
- Prefer official sources and source-native retrieval.
- Cache or mirror only with explicit permission and preserved obligations.
- Keep provenance, policy evidence, and versions inspectable.
- Standardize access and representations without erasing modality-specific structure.
- Make every policy decision explainable and overrideable only through explicit configuration.
