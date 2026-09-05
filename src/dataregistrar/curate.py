"""Create and verify overlays. The CLI is a thin wrapper over this module.

An overlay becomes `verified` only when every item of the checklist in
docs/vision.md section 5.4 is recorded. Nothing here guesses.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from dataregistrar._yaml import dump_yaml, load_yaml
from dataregistrar.download import sha256_of
from dataregistrar.model import Confidence, Distribution, Kind, License, Overlay, Record, Status
from dataregistrar.policy import derive_rights
from dataregistrar.registry import Layer, Registry

UrlCheck = Callable[[str], bool]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def default_canonical(record: Record) -> str:
    return f"{record.source}-{slug(record.name)}"


def overlay_path(layer: Layer, canonical: str) -> Path:
    return layer.overlays_dir / f"{canonical}.yaml"


def default_url_ok(url: str) -> bool:
    try:
        with (
            httpx.Client(follow_redirects=True, timeout=20) as client,
            client.stream("GET", url) as r,
        ):
            return r.status_code < 400
    except httpx.HTTPError:
        return False


def load_overlay(path: Path) -> Overlay:
    raw: Any = load_yaml(path)
    return Overlay.model_validate(raw)


def write_overlay(overlay: Overlay, path: Path) -> None:
    data = overlay.model_dump(mode="json", exclude_none=True, exclude={"layer"})
    for dist in data.get("distributions", []):
        if not dist.get("checksums"):
            dist.pop("checksums", None)
    dump_yaml(data, path)


def create_overlay(
    registry: Registry,
    record_id: str,
    *,
    layer: Layer,
    canonical: str | None = None,
    spdx: str | None = None,
    evidence_url: str | None = None,
    cite_as: str | None = None,
    force: bool = False,
) -> Path:
    """Write a new overlay pre-filled from the live record. Status stays `imported`."""
    record = registry.annotate(
        registry.adapter(record_id.partition(":")[0], fresh=True).get(record_id.partition(":")[2])
    )
    canonical = canonical or record.canonical or default_canonical(record)
    path = overlay_path(layer, canonical)
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass force=True to overwrite")
    license = License(
        spdx=spdx or record.license.spdx,
        evidence_url=evidence_url or record.license.evidence_url,  # type: ignore[arg-type]
    )
    overlay = Overlay(
        canonical=canonical,
        kind=record.kind,
        name=record.name,
        publisher=record.publisher,
        cite_as=cite_as or record.cite_as,
        distributions=[Distribution(id=record.id, role="official")],
        license=license if license.spdx or license.evidence_url else None,
        status=Status.IMPORTED,
    )
    write_overlay(overlay, path)
    return path


def link_distribution(
    registry: Registry,
    path: Path,
    record_id: str,
    *,
    role: str,
    modifications: str | None = None,
) -> Overlay:
    """Add a mirror, conversion, or subset to an existing overlay. The record must resolve."""
    overlay = load_overlay(path)
    if any(d.id == record_id for d in overlay.distributions):
        raise ValueError(f"{record_id} is already a distribution of {overlay.canonical}")
    source, _, native = record_id.partition(":")
    registry.adapter(source, fresh=True).get(native)  # raises if it does not exist
    dist = Distribution.model_validate(
        {"id": record_id, "role": role, "modifications": modifications}
    )
    overlay = overlay.model_copy(update={"distributions": [*overlay.distributions, dist]})
    write_overlay(overlay, path)
    return overlay


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Verification:
    path: Path
    overlay: Overlay
    checks: list[Check] = field(default_factory=list[Check])

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)


def verify_overlay(
    registry: Registry,
    path: Path,
    *,
    by: str,
    today: date | None = None,
    url_ok: UrlCheck = default_url_ok,
    workdir: Path | None = None,
    releases: list[str] | None = None,
) -> Verification:
    """Run the checklist. On full pass, write the overlay back as `verified`.

    On any failure the file is left untouched and the checks say what is missing. For a
    series, the latest release is retrieved unless `releases` names specific ones. Checksums
    are merged with those already recorded, never dropped, so earlier issues stay known.
    """
    overlay = load_overlay(path)
    result = Verification(path=path, overlay=overlay)
    checks = result.checks

    official = next((d for d in overlay.distributions if d.role == "official"), None)
    if official is None:
        checks.append(Check("official distribution", False, "no distribution has role: official"))
        return result
    source, _, native = official.id.partition(":")
    try:
        record = registry.adapter(source, fresh=True).get(native)
    except Exception as err:
        checks.append(Check("official distribution", False, f"cannot fetch {official.id}: {err}"))
        return result
    checks.append(Check("official distribution", True, official.id))

    # 1. license with evidence at an official URL
    lic = overlay.license
    if lic is None or not lic.spdx:
        checks.append(Check("license", False, "license.spdx is not set"))
    elif lic.evidence_url is None:
        checks.append(Check("license", False, "license.evidence_url is not set"))
    elif not url_ok(str(lic.evidence_url)):
        checks.append(Check("license", False, f"evidence URL does not resolve: {lic.evidence_url}"))
    else:
        checks.append(Check("license", True, f"{lic.spdx}, evidence {lic.evidence_url}"))

    # 2. official source URL resolves
    if record.url is None:
        checks.append(Check("source url", False, "record has no url"))
    elif not url_ok(str(record.url)):
        checks.append(Check("source url", False, f"does not resolve: {record.url}"))
    else:
        checks.append(Check("source url", True, str(record.url)))

    # 3 + 4. retrieval through the adapter for every distribution, checksums recorded
    new_checksums: dict[str, dict[str, str]] = {}
    if (overlay.kind or record.kind) in {Kind.DATASET, Kind.RELEASE_SERIES}:
        selectors: list[str | None] = list(releases) if releases else [None]
        for dist in overlay.distributions:
            d_source, _, d_native = dist.id.partition(":")
            try:
                adapter = registry.adapter(d_source, fresh=True)
                d_record = record if dist is official else adapter.get(d_native)
                got: dict[str, str] = {}
                for selector in selectors if dist is official else [None]:
                    plan = adapter.resolve(d_record, selector)
                    with tempfile.TemporaryDirectory() as tmp:
                        paths = adapter.retrieve(plan, workdir or Path(tmp))
                        got.update(
                            {
                                planned.filename: sha256_of(p)
                                for planned, p in zip(plan.files, paths, strict=True)
                            }
                        )
                new_checksums[dist.id] = got
                checks.append(
                    Check(f"retrieval {dist.role}", True, f"{len(got)} file(s) via {dist.id}")
                )
            except Exception as err:
                checks.append(Check(f"retrieval {dist.role}", False, f"{dist.id}: {err}"))
        total = sum(len(v) for v in new_checksums.values())
        checks.append(Check("checksums", total > 0, f"{total} recorded this run"))
    else:
        checks.append(Check("retrieval", True, "not applicable to this kind"))
        checks.append(Check("checksums", True, "not applicable to this kind"))

    # 5. citation
    cite_as = overlay.cite_as or record.cite_as
    checks.append(Check("citation", bool(cite_as), cite_as or "no cite_as on overlay or record"))

    # 6. reviewer
    checks.append(Check("reviewer", bool(by.strip()), by or "pass --by"))

    if not result.passed:
        return result

    assert lic is not None
    verified_license = lic.model_copy(
        update={"verified_at": today or date.today(), "verified_by": by}
    )
    rights = (overlay.rights or derive_rights(verified_license)).model_copy(
        update={"confidence": Confidence.VERIFIED}
    )
    distributions: list[Distribution] = []
    for d in overlay.distributions:
        merged = {**d.checksums, **new_checksums.get(d.id, {})}
        single = next(iter(merged.values())) if len(merged) == 1 else None
        distributions.append(d.model_copy(update={"sha256": single, "checksums": merged}))
    result.overlay = overlay.model_copy(
        update={
            "license": verified_license,
            "rights": rights,
            "cite_as": cite_as,
            "distributions": distributions,
            "status": Status.VERIFIED,
        }
    )
    write_overlay(result.overlay, path)
    return result
