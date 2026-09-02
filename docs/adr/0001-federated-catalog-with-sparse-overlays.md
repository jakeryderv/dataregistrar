# ADR 0001: Federated catalog with sparse overlays, not a registry-first catalog

**Status:** accepted, 2026-09-01

## Context

The original charter made a hand-curated registry the center of the system: adapters fed candidates into it, `search()` queried only the registry, and a separate `discover()` queried live providers. A first rewrite kept that model and made it concrete as one git-tracked record file per dataset.

Two problems surfaced in discussion:

1. Hubs such as Hugging Face hold hundreds of thousands of datasets. A record per dataset does not scale and is not where the value is; hubs already expose search and metadata behind APIs.
2. The project should not be limited to static datasets. Government release series, query APIs, and eventually streams need the same interface. A registry of static records fits those poorly.

At the same time, the licensing focus requires human-verified claims. Hub license tags are unreliable, so some reviewed layer is unavoidable.

## Decision

- **Adapters decide what exists.** A source is in the catalog by virtue of having an adapter. Nothing is written per hub dataset.
- **The registry decides which sources are in play.** It is a short `sources.yaml` listing enabled adapters and configuring one-off sources. It is never a gate on what appears.
- **Overlays decide what has been checked.** An overlay is an optional, per-record file carrying human-verified facts: license with evidence, citation, canonical grouping of mirrors. Overlays are sparse.
- **Every result carries a confidence status.** Adapter results are `imported`; overlay-backed results that pass the verification checklist are `verified`. One `search()` serves both, filterable by `min_status`.
- **Every record has a `kind`** (`dataset`, `release-series`, `query-api`, `stream`) so non-dataset sources need no schema change later.
- **All three layers are user-extensible** and resolve in layers: built-in, user or org, project. Shipped defaults get no special treatment.

## Consequences

- Search is live and federated, so it depends on source availability and needs a response cache with per-source TTL.
- Cross-source canonicalization is opt-in and only exists where an overlay creates it. Duplicates across mirrors remain visible until someone groups them.
- Policy filtering on `imported` rights is allowed but flagged; trustworthy filtering requires overlays, so curation throughput remains a product metric.
- The `discover()` operation from the original charter is removed; its role is served by status filtering.
- Sources and overlays are small enough to live as files in git with CI validation. Adapter results are never committed.
- Rights for `query-api` and `stream` kinds are based on terms of service, start as `unknown`, and require an overlay to assert anything.

## Alternatives considered

- **Registry-first with per-dataset files.** Rejected: does not scale to hubs, front-loads curation before anything is usable, and fits non-dataset kinds poorly.
- **Pure pass-through meta-search with no reviewed layer.** Rejected: rights filtering would be only as good as hub metadata, which defeats the licensing focus.
