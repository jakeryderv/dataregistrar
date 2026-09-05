from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

import dataregistrar
from dataregistrar import curate
from dataregistrar.adapters import AccessRequired, NoRetrievalPath
from dataregistrar.download import ChecksumMismatch
from dataregistrar.model import Record, Status
from dataregistrar.policy import DatasetPolicyError
from dataregistrar.registry import Layer
from dataregistrar.registry.layers import project_layer, user_layer

app = typer.Typer(
    name="dreg",
    help="Discover, evaluate, and retrieve public data across providers.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dreg {dataregistrar.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Discover, evaluate, and retrieve public data across providers."""


def _fmt_right(value: bool | str) -> str:
    return {True: "yes", False: "no"}.get(value, "?") if isinstance(value, bool) else "?"


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Free-text query.")],
    source: Annotated[
        list[str] | None, typer.Option("--source", "-s", help="Restrict to these source ids.")
    ] = None,
    policy: Annotated[
        str | None, typer.Option("--policy", "-p", help="Policy preset, e.g. commercial.")
    ] = None,
    min_status: Annotated[
        Status | None, typer.Option("--min-status", help="Drop records below this status.")
    ] = None,
    fresh: Annotated[bool, typer.Option("--fresh", help="Bypass the response cache.")] = False,
) -> None:
    """Search every enabled source and show what came back, with confidence and rights."""
    records = dataregistrar.search(
        query, sources=source, policy=policy, min_status=min_status, fresh=fresh
    )
    if not records:
        console.print("[yellow]no results[/yellow]")
        raise typer.Exit(code=1)
    table = Table(box=None, pad_edge=False)
    for col in ("id", "status", "license", "commercial", "confidence"):
        table.add_column(col)
    for r in records:
        table.add_row(
            r.id,
            r.status,
            r.license.spdx or "unknown",
            _fmt_right(r.rights.commercial_use),
            r.rights.confidence,
        )
    console.print(table)


def _print_record(r: Record) -> None:
    console.print(f"[bold]{r.name}[/bold]  ({r.id}, {r.kind}, {r.status})")
    if r.canonical:
        console.print(f"canonical:   {r.canonical}")
    console.print(f"source:      {r.source}")
    if r.url:
        console.print(f"url:         {r.url}")
    if r.publisher:
        console.print(f"publisher:   {r.publisher}")
    if r.cite_as:
        console.print(f"cite:        {r.cite_as}")
    lic = r.license
    console.print(f"license:     {lic.spdx or 'unknown'}")
    if lic.evidence_url:
        console.print(f"  evidence:  {lic.evidence_url}")
    if lic.verified_at:
        console.print(f"  verified:  {lic.verified_at} by {lic.verified_by or '?'}")
    console.print(f"rights ({r.rights.confidence}):")
    for right in ("commercial_use", "redistribution", "derivatives", "model_training"):
        console.print(f"  {right:<20} {_fmt_right(r.rights.value(right))}")
    if not r.access.retrievable:
        console.print("retrieval:   [yellow]no retrieval path in this adapter yet[/yellow]")
    if r.series is not None:
        s = r.series
        console.print("series:")
        if s.cadence:
            console.print(f"  cadence:   {s.cadence}")
        if s.revision_policy:
            console.print(f"  revisions: {s.revision_policy}")
        if s.releases:
            latest = s.latest()
            first = min(x.id for x in s.releases)
            console.print(f"  releases:  {len(s.releases)} ({first}..{latest.id})")
            console.print(
                f"  latest:    {latest.id}, revision {latest.revision}, {latest.filename}"
            )
            for x in s.releases:
                if x.supersedes:
                    console.print(
                        f"  [yellow]re-issued[/yellow] {x.id}: {x.filename} "
                        f"supersedes {x.supersedes}"
                    )
    if r.description:
        console.print(f"\n{r.description}")


@app.command()
def get(
    record_id: Annotated[str, typer.Argument(help="Record id, e.g. uci:186.")],
    policy: Annotated[
        str | None, typer.Option("--policy", "-p", help="Fail unless this preset is satisfied.")
    ] = None,
    fresh: Annotated[bool, typer.Option("--fresh", help="Bypass the response cache.")] = False,
) -> None:
    """Show one record. With --policy, exit non-zero and explain if it does not qualify."""
    try:
        _print_record(dataregistrar.get(record_id, policy=policy, fresh=fresh))
    except DatasetPolicyError as err:
        console.print("[red]DatasetPolicyError[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=2) from None


@app.command()
def fetch(
    record_id: Annotated[str, typer.Argument(help="Record id, e.g. uci:186.")],
    dest: Annotated[
        Path | None, typer.Option("--dest", "-d", help="Directory to download into.")
    ] = None,
    policy: Annotated[
        str | None, typer.Option("--policy", "-p", help="Refuse unless this preset is satisfied.")
    ] = None,
    release: Annotated[
        str | None,
        typer.Option("--release", "-r", help="Series only: a release id, default latest."),
    ] = None,
) -> None:
    """Download a record's files, verify checksums where known, and print what you owe."""
    try:
        local = dataregistrar.retrieve(record_id, destination=dest, policy=policy, release=release)
    except DatasetPolicyError as err:
        console.print("[red]DatasetPolicyError[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=2) from None
    except ChecksumMismatch as err:
        console.print("[red]ChecksumMismatch[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=3) from None
    except AccessRequired as err:
        console.print("[red]AccessRequired[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=4) from None
    except (NoRetrievalPath, KeyError) as err:
        console.print("[red]NoRetrievalPath[/red]\n")
        console.print(str(err).strip("'"), highlight=False)
        raise typer.Exit(code=5) from None
    for planned, path in zip(local.plan.files, local.paths, strict=True):
        verified = "checksum verified" if planned.sha256 else "no recorded checksum"
        console.print(f"{path}  [dim]({verified})[/dim]")
    console.print()
    console.print(local.attribution, highlight=False)


cache_app = typer.Typer(help="Inspect or clear the response cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")


@cache_app.command("info")
def cache_info() -> None:
    """Where the cache lives and how many responses it holds."""
    registry = dataregistrar.default_registry()
    if registry.cache is None:
        console.print("no cache configured")
        return
    console.print(f"path:    {registry.cache.path}")
    console.print(f"entries: {registry.cache.count()}")
    for source_id in registry.source_ids:
        ttl = registry.source_configs[source_id].cache_ttl
        console.print(
            f"  {source_id:<8} {registry.cache.count(source_id):>5} entries, ttl {ttl:g}s"
        )


@cache_app.command("clear")
def cache_clear(
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Only this source id.")
    ] = None,
) -> None:
    """Drop cached responses, for one source or all."""
    registry = dataregistrar.default_registry()
    if registry.cache is None:
        console.print("no cache configured")
        return
    removed = registry.cache.clear(source)
    console.print(f"removed {removed} cached response(s)")


overlay_app = typer.Typer(help="Create, verify, and list overlays.", no_args_is_help=True)
app.add_typer(overlay_app, name="overlay")


def _target_layer(layer: str, directory: Path | None) -> Layer:
    if directory is not None:
        return Layer("custom", directory)
    if layer == "user":
        return user_layer()
    if layer == "project":
        return project_layer()
    raise typer.BadParameter("layer must be 'project' or 'user', or pass --dir")


@overlay_app.command("create")
def overlay_create(
    record_id: Annotated[str, typer.Argument(help="Record to overlay, e.g. uci:186.")],
    canonical: Annotated[
        str | None, typer.Option(help="Canonical id. Default: source-name.")
    ] = None,
    spdx: Annotated[str | None, typer.Option(help="License SPDX id, if you know it.")] = None,
    evidence: Annotated[str | None, typer.Option(help="URL where the license is stated.")] = None,
    cite: Annotated[str | None, typer.Option(help="Citation, if the source lacks one.")] = None,
    layer: Annotated[str, typer.Option(help="project or user")] = "project",
    directory: Annotated[
        Path | None, typer.Option("--dir", help="Write into this layer dir.")
    ] = None,
    force: Annotated[bool, typer.Option(help="Overwrite an existing overlay.")] = False,
) -> None:
    """Write a new overlay pre-filled from the live record. It stays `imported` until verified."""
    try:
        path = curate.create_overlay(
            dataregistrar.default_registry(),
            record_id,
            layer=_target_layer(layer, directory),
            canonical=canonical,
            spdx=spdx,
            evidence_url=evidence,
            cite_as=cite,
            force=force,
        )
    except FileExistsError as err:
        console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=1) from None
    console.print(f"wrote {path}")
    console.print(
        "edit license.spdx and license.evidence_url if missing, then: dreg overlay verify"
    )


@overlay_app.command("verify")
def overlay_verify(
    canonical: Annotated[str, typer.Argument(help="Canonical id of the overlay.")],
    by: Annotated[str, typer.Option(help="Who reviewed it. Recorded on the overlay.")],
    layer: Annotated[str, typer.Option(help="project or user")] = "project",
    directory: Annotated[
        Path | None, typer.Option("--dir", help="Layer dir holding the overlay.")
    ] = None,
    release: Annotated[
        list[str] | None,
        typer.Option("--release", "-r", help="Series only: releases to record. Default latest."),
    ] = None,
) -> None:
    """Run the verification checklist. Marks the overlay verified only if every check passes."""
    path = curate.overlay_path(_target_layer(layer, directory), canonical)
    if not path.is_file():
        console.print(f"[red]no overlay at {path}[/red]")
        raise typer.Exit(code=1)
    result = curate.verify_overlay(dataregistrar.default_registry(), path, by=by, releases=release)
    for check in result.checks:
        mark = "[green]ok[/green]  " if check.ok else "[red]FAIL[/red]"
        console.print(f"{mark} {check.name:<22} {check.detail}", highlight=False)
    if result.passed:
        console.print(f"\n[green]verified[/green] {canonical} → {path}")
    else:
        console.print(f"\n[yellow]not verified[/yellow]; {path} left unchanged")
        raise typer.Exit(code=1)


@overlay_app.command("link")
def overlay_link(
    canonical: Annotated[str, typer.Argument(help="Canonical id of the existing overlay.")],
    record_id: Annotated[str, typer.Argument(help="Record to add, e.g. hf:org/name.")],
    role: Annotated[str, typer.Option(help="mirror, conversion, or subset")] = "mirror",
    modifications: Annotated[
        str | None, typer.Option(help="How it differs from the official distribution.")
    ] = None,
    layer: Annotated[str, typer.Option(help="project or user")] = "project",
    directory: Annotated[
        Path | None, typer.Option("--dir", help="Layer dir holding the overlay.")
    ] = None,
) -> None:
    """Add a mirror, conversion, or subset to an existing overlay so it groups under one
    canonical id. Run verify afterwards to record its checksums."""
    path = curate.overlay_path(_target_layer(layer, directory), canonical)
    if not path.is_file():
        console.print(f"[red]no overlay at {path}[/red]")
        raise typer.Exit(code=1)
    try:
        overlay = curate.link_distribution(
            dataregistrar.default_registry(),
            path,
            record_id,
            role=role,
            modifications=modifications,
        )
    except Exception as err:
        console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=1) from None
    console.print(f"{canonical} now has {len(overlay.distributions)} distributions:")
    for d in overlay.distributions:
        console.print(f"  {d.role:<11} {d.id}")


@overlay_app.command("list")
def overlay_list() -> None:
    """Every overlay visible from the current layers, with where it came from."""
    registry = dataregistrar.default_registry()
    table = Table(box=None, pad_edge=False)
    for col in ("canonical", "status", "license", "layer", "distributions"):
        table.add_column(col)
    for o in sorted(registry.overlays, key=lambda o: o.canonical):
        spdx = o.license.spdx if o.license and o.license.spdx else "unknown"
        table.add_row(
            o.canonical,
            o.status or "-",
            spdx,
            o.layer or "-",
            ", ".join(d.id for d in o.distributions),
        )
    console.print(table)
