from pathlib import Path

import pytest
from pydantic import HttpUrl

from dataregistrar.model import AccessPlan, Kind, License, PlannedFile, Record, Rights
from dataregistrar.representations import LocalDataset

CSV = "x,y,label\n1,2.5,red\n3,4.5,white\n"


def _local(tmp_path: Path, names: list[str], **record_fields: object) -> LocalDataset:
    paths: list[Path] = []
    for name in names:
        path = tmp_path / name
        path.write_text(CSV)
        paths.append(path)
    record = Record.model_validate(
        {"id": "x:1", "kind": Kind.DATASET, "source": "x", "name": "n", **record_fields}
    )
    plan = AccessPlan(
        record_id="x:1",
        kind=Kind.DATASET,
        files=[PlannedFile(url=HttpUrl(f"https://x.test/{n}"), filename=n) for n in names],
    )
    return LocalDataset(record=record, plan=plan, paths=paths)


def test_pandas_arrow_numpy_agree_on_shape(tmp_path: Path) -> None:
    local = _local(tmp_path, ["d.csv"])
    df = local.as_pandas()
    assert df.shape == (2, 3)
    assert list(df.columns) == ["x", "y", "label"]
    assert local.as_arrow().num_rows == 2
    assert local.as_numpy().shape == (2, 3)


def test_several_tabular_files_require_a_filename(tmp_path: Path) -> None:
    local = _local(tmp_path, ["a.csv", "b.csv"])
    with pytest.raises(ValueError, match="several tabular files"):
        local.as_pandas()
    assert local.as_pandas(filename="b.csv").shape == (2, 3)
    with pytest.raises(FileNotFoundError):
        local.as_pandas(filename="zzz.csv")


def test_attribution_never_overstates(tmp_path: Path) -> None:
    unknown = _local(tmp_path, ["d.csv"])
    assert "License: unknown" in unknown.attribution
    assert "unknown; cite to be safe" in unknown.attribution

    known = _local(
        tmp_path,
        ["d.csv"],
        license=License(spdx="CC-BY-4.0"),
        rights=Rights(attribution_required=True),
        cite_as="Someone (2009)",
    )
    assert "License: CC-BY-4.0" in known.attribution
    assert "Attribution required." in known.attribution
    assert "Cite: Someone (2009)" in known.attribution
