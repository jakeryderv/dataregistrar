# ADR 0002: Tooling and packaging baseline

**Status:** accepted, 2026-09-01.

## Context

The project is a Python SDK first. The machine already has `uv`, `just`, `ruff`, and `pyright`; the repo has a GitHub remote; the name `dataregistrar` is unclaimed on PyPI as of this date.

## Decision

| Concern | Choice |
|---|---|
| Python | 3.11 minimum |
| Env, lock, build, publish | `uv`, `uv_build` backend |
| Record models and schema export | `pydantic` v2 |
| YAML | `ruamel.yaml` (round-trips comments in human-edited files) |
| HTTP | `httpx` |
| Response cache | stdlib `sqlite3` |
| CLI | `typer` + `rich` |
| Config and cache dirs | `platformdirs` |
| Tests | `pytest`, `pytest-recording` cassettes; tests never hit live sources |
| Lint, format, types | `ruff`, `pyright` |
| Tasks, CI | `justfile`, GitHub Actions |
| Distribution | PyPI `dataregistrar`, semver from 0.1.0, trusted publishing via GitHub OIDC |
| Plugins | entry-point group `dataregistrar.adapters`; third-party packages named `dataregistrar-<name>` |

The core package depends on none of pandas, pyarrow, or provider SDKs. Those are optional extras: `[huggingface]`, `[uci]`, `[pandas]`, `[arrow]`, `[all]`.

## Consequences

- JSON schemas for overlays and sources are generated from the pydantic models and exported in CI; the models are the source of truth.
- Shipped adapters register through the same entry-point mechanism as third-party ones, so the plugin path is exercised from day one.
- Built-in sources and overlays live inside the package so they ship in the wheel.

## Resolved items

1. **Project license: Apache-2.0.** Chosen for the patent grant, given the org-layer use case. `LICENSE` at repo root is the verbatim text from apache.org.
2. **Models library: pydantic v2.** Confirmed. Schema export for CI validation of overlays and sources is the deciding benefit.

## Next step

Scaffold the day-one project set, then a walking skeleton: one adapter, one record, one search, one policy check, end to end with a recorded cassette.
