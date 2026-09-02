# dataregistrar

Provider-agnostic catalog and access layer for public data. One interface to discover, evaluate, retrieve, and load data from many sources, with licensing, provenance, and source metadata preserved and inspectable.

**Status: pre-alpha.** The package on PyPI is a skeleton that reserves the name and ships the record model. Nothing searches or retrieves yet. See [docs/vision.md](docs/vision.md) for where this is going.

## Install

```bash
pip install dataregistrar
dreg --version
```

## Develop

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
git clone git@github.com:jakeryderv/dataregistrar.git
cd dataregistrar
just setup     # install toolchain and dependencies
just test      # run tests
just check     # format check, lint, types, tests; this is what CI runs
just fmt       # apply formatting and autofixes
just run -- --version
```

## Documentation

- [docs/vision.md](docs/vision.md): what this is and why
- [docs/architecture.md](docs/architecture.md): modules, layout, runtime flow
- [docs/adr/](docs/adr/): decision records

## License

Apache-2.0. See [LICENSE](LICENSE).
