"""HTTP download with checksum verification. Shared by adapters; depends only on model."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from dataregistrar.model import AccessPlan, PlannedFile

CHUNK = 1 << 16


class ChecksumMismatch(Exception):
    def __init__(self, path: Path, expected: str, actual: str) -> None:
        self.path, self.expected, self.actual = path, expected, actual
        super().__init__(
            f"checksum mismatch for {path.name}\n  expected: {expected}\n  actual:   {actual}"
        )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(client: httpx.Client, planned: PlannedFile, destination: Path) -> Path:
    """Fetch one file. Reuses an existing file when its checksum matches or none is expected."""
    target = destination / planned.filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and (planned.sha256 is None or sha256_of(target) == planned.sha256):
        return target

    partial = target.with_name(target.name + ".part")
    # Hubs commonly redirect file URLs to a CDN. httpx drops Authorization on cross-origin hops.
    with client.stream("GET", str(planned.url), follow_redirects=True) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(CHUNK):
                handle.write(chunk)

    actual = sha256_of(partial)
    if planned.sha256 is not None and actual != planned.sha256:
        partial.unlink()
        raise ChecksumMismatch(target, planned.sha256, actual)
    partial.replace(target)
    return target


def download_all(client: httpx.Client, plan: AccessPlan, destination: Path) -> list[Path]:
    return [download(client, planned, destination) for planned in plan.files]
