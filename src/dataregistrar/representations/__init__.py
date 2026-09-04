"""Local, retrieved data and the representations it can take. Loaders import lazily."""

from __future__ import annotations

import csv as _csv
import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dataregistrar.model import AccessPlan, Record

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    import pyarrow as pa

TABULAR_SUFFIXES = {".csv", ".parquet", ".csv.gz"}


def _tabular_suffix(path: Path) -> str | None:
    name = path.name.lower()
    return next(
        (s for s in sorted(TABULAR_SUFFIXES, key=len, reverse=True) if name.endswith(s)), None
    )


SNIFF_BYTES = 8192


def sniff_delimiter(path: Path) -> str:
    """Detect the delimiter from the file head. Providers ship ';' and '\t' as '.csv' routinely."""
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        sample = handle.read(SNIFF_BYTES)
    try:
        return _csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except _csv.Error:
        return ","


class MissingExtra(ImportError):
    def __init__(self, package: str, extra: str) -> None:
        super().__init__(
            f"{package} is not installed. Install it with: pip install 'dataregistrar[{extra}]'"
        )


@dataclass(frozen=True)
class LocalDataset:
    """A retrieved `dataset` record: its files on disk plus the record they came from."""

    record: Record
    plan: AccessPlan
    paths: list[Path]

    def files(self) -> list[Path]:
        return list(self.paths)

    @property
    def attribution(self) -> str:
        """What the user owes, in one string. Never claims more than the record knows."""
        lines: list[str] = []
        spdx = self.record.license.spdx or "unknown"
        lines.append(f"License: {spdx} (confidence: {self.record.rights.confidence})")
        required = self.record.rights.attribution_required
        if required is True:
            lines.append("Attribution required.")
        elif required == "unknown":
            lines.append("Attribution requirement unknown; cite to be safe.")
        if self.record.cite_as:
            lines.append(f"Cite: {self.record.cite_as}")
        return "\n".join(lines)

    def _tabular_file(self, filename: str | None) -> Path:
        candidates = [p for p in self.paths if _tabular_suffix(p) is not None]
        if filename is not None:
            for path in candidates:
                if path.name == filename or path.as_posix().endswith("/" + filename):
                    return path
            raise FileNotFoundError(f"{filename!r} is not a tabular file of {self.record.id}")
        if not candidates:
            raise ValueError(f"{self.record.id} has no tabular files; use files()")
        if len(candidates) > 1:
            names = ", ".join(p.name for p in candidates)
            raise ValueError(
                f"{self.record.id} has several tabular files ({names}); pass filename="
            )
        return candidates[0]

    def as_pandas(self, filename: str | None = None) -> pd.DataFrame:
        try:
            import pandas as pd
        except ImportError:
            raise MissingExtra("pandas", "pandas") from None
        path = self._tabular_file(filename)
        if _tabular_suffix(path) == ".parquet":
            try:
                return pd.read_parquet(path)
            except ImportError:
                raise MissingExtra("pyarrow", "arrow") from None
        return pd.read_csv(path, sep=sniff_delimiter(path))

    def as_arrow(self, filename: str | None = None) -> pa.Table:
        try:
            from pyarrow import csv, parquet
        except ImportError:
            raise MissingExtra("pyarrow", "arrow") from None
        path = self._tabular_file(filename)
        if _tabular_suffix(path) == ".parquet":
            return parquet.read_table(str(path))  # pyright: ignore[reportUnknownMemberType]
        return csv.read_csv(
            str(path), parse_options=csv.ParseOptions(delimiter=sniff_delimiter(path))
        )

    def as_numpy(
        self, filename: str | None = None
    ) -> np.ndarray[tuple[int, ...], np.dtype[np.generic]]:
        return self.as_pandas(filename).to_numpy()


__all__ = ["LocalDataset", "MissingExtra"]
