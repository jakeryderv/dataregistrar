# Agent notes

Setup, build, and test commands live in [README.md](README.md). Do not duplicate them here.

## Where things are

- `docs/vision.md`: what this is and the v1 scope. Read it before designing anything.
- `docs/architecture.md`: modules, dependency direction, layout, runtime flow.
- `docs/adr/`: why the design looks the way it does. Append-only.
- `src/dataregistrar/`: the package. `model` has no I/O; dependencies point downward only (`cli → federated → registry → adapters → model`). The module is `federated`, not `search`, because `dataregistrar.search()` is the SDK function.
- `tests/unit/` for pure logic, `tests/contract/` for the adapter suite, `tests/cassettes/` for recorded HTTP.

## Constraints

- Tests never hit live sources and never mirror data contents. pytest runs with `--block-network`; Metadata HTTP goes through cassettes in `tests/cassettes/`; file downloads in tests are served by a fixture transport with a tiny synthetic CSV, never a real file. Re-record with `just record` only when an adapter or a source changes.
- The core package must not depend on pandas, pyarrow, or any provider SDK. Those are optional extras.
- Rights that are missing or unclear are `unknown`, never inferred. `imported` must never look `verified`.
- Nothing is written to git per hub dataset. Only sources and overlays are files. Overlays are written by `dreg overlay create` and promoted by `dreg overlay verify`, never marked verified by hand.
- `just check` must pass before a PR. It is what CI runs.

## Conventions

- Conventional Commits. No Co-Authored-By or AI attribution lines.
- Short-lived branches named `feat/…`, `fix/…`, `docs/…`, merged to `main` by PR.
- A design choice that gets argued about becomes an ADR before it becomes code.
