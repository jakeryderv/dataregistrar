"""Local, retrieved data and the representations it can take. Loaders import lazily."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dataregistrar.model import AccessPlan, Record

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    import pyarrow as pa

TABULAR_SUFFIXES = {".csv"}


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
        candidates = [p for p in self.paths if p.suffix.lower() in TABULAR_SUFFIXES]
        if filename is not None:
            for path in candidates:
                if path.name == filename:
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
        return pd.read_csv(self._tabular_file(filename))

    def as_arrow(self, filename: str | None = None) -> pa.Table:
        try:
            from pyarrow import csv
        except ImportError:
            raise MissingExtra("pyarrow", "arrow") from None
        return csv.read_csv(str(self._tabular_file(filename)))

    def as_numpy(
        self, filename: str | None = None
    ) -> np.ndarray[tuple[int, ...], np.dtype[np.generic]]:
        return self.as_pandas(filename).to_numpy()


__all__ = ["LocalDataset", "MissingExtra"]
