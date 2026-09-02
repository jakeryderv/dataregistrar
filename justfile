set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install the toolchain and dependencies.
setup:
    uv sync --all-groups

# Run the test suite.
test:
    uv run pytest

# Format, lint, and type-check without modifying files. CI runs this.
check:
    uv run ruff format --check .
    uv run ruff check .
    uv run pyright
    uv run pytest

# Apply formatting and autofixable lint.
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Re-record HTTP cassettes against live sources. Only when an adapter or source changes.
record:
    rm -f tests/cassettes/*.yaml
    uv run pytest tests/contract tests/e2e -o addopts="" --record-mode=once

# Build sdist and wheel into dist/.
build:
    rm -rf dist
    uv build

# Run the CLI with arguments, e.g. `just run --version`.
run *args:
    uv run dreg {{args}}
