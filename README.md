# dataregistrar

Provider-agnostic catalog and access layer for public data. One interface to discover, evaluate, retrieve, and load data from many sources, with licensing, provenance, and source metadata preserved and inspectable.

**Status: pre-alpha.** Two adapters (UCI and Hugging Face), a licensing policy engine, a verified overlay layer, and checksum-verified retrieval into pandas, Arrow, or NumPy. See [docs/vision.md](docs/vision.md) for where this is going.

## Install

```bash
pip install dataregistrar            # core: search, policy, download
pip install 'dataregistrar[pandas]'   # plus as_pandas() and as_numpy()
pip install 'dataregistrar[all]'      # plus as_arrow()
dreg --version
```

## Usage

```bash
dreg search wine                        # every enabled source, with confidence and rights
dreg search wine --policy commercial    # only records whose rights are known to allow it
dreg get uci:186                        # one record with license evidence
dreg get uci:109 --policy commercial    # exits 2 and explains why it does not qualify
dreg fetch uci:186 --policy commercial  # downloads, verifies the checksum, prints what you owe
```

```python
import dataregistrar as dr

for record in dr.search("wine", policy="commercial"):
    print(record.id, record.license.spdx, record.rights.confidence)

wine = dr.retrieve("uci:186", policy="commercial")   # refuses before downloading if not permitted
df = wine.as_pandas()                                 # needs dataregistrar[pandas]
print(wine.attribution)
```

Retrieval is source-native: files come from the provider, land in your user cache, and are verified against the checksum an overlay recorded. Nothing is mirrored.

Rights that a source does not state are `unknown`, and unknown never satisfies a policy. Rights a source does declare, like a Hugging Face license tag, are derived at `imported` confidence. A record only becomes `verified` through an overlay a person wrote with evidence. UCI's API, for example, exposes no license at all; the shipped overlay for Wine Quality is what makes it pass `--policy commercial`. Use `--min-status verified` when self-declared tags are not enough.

Gated Hugging Face datasets import as `restricted` and are not downloaded without `HF_TOKEN` set.

## Develop

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
git clone git@github.com:jakeryderv/dataregistrar.git
cd dataregistrar
just setup     # install toolchain and dependencies
just test      # run tests
just check     # format check, lint, types, tests; this is what CI runs
just fmt       # apply formatting and autofixes
just record    # re-record HTTP cassettes against live sources
just run -- search wine
```

## Documentation

- [docs/vision.md](docs/vision.md): what this is and why
- [docs/architecture.md](docs/architecture.md): modules, layout, runtime flow
- [docs/adr/](docs/adr/): decision records

## License

Apache-2.0. See [LICENSE](LICENSE).
