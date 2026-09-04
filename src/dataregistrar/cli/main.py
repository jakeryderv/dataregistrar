from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

import dataregistrar
from dataregistrar.download import ChecksumMismatch
from dataregistrar.model import Record, Status
from dataregistrar.policy import DatasetPolicyError

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
) -> None:
    """Search every enabled source and show what came back, with confidence and rights."""
    records = dataregistrar.search(query, sources=source, policy=policy, min_status=min_status)
    if not records:
        console.print("[yellow]no results[/yellow]")
        raise typer.Exit(code=1)
    table = Table(box=None, pad_edge=False)
    for col in ("id", "name", "status", "license", "commercial", "confidence"):
        table.add_column(col)
    for r in records:
        table.add_row(
            r.id,
            r.name,
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
    if r.description:
        console.print(f"\n{r.description}")


@app.command()
def get(
    record_id: Annotated[str, typer.Argument(help="Record id, e.g. uci:186.")],
    policy: Annotated[
        str | None, typer.Option("--policy", "-p", help="Fail unless this preset is satisfied.")
    ] = None,
) -> None:
    """Show one record. With --policy, exit non-zero and explain if it does not qualify."""
    try:
        _print_record(dataregistrar.get(record_id, policy=policy))
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
) -> None:
    """Download a record's files, verify checksums where known, and print what you owe."""
    try:
        local = dataregistrar.retrieve(record_id, destination=dest, policy=policy)
    except DatasetPolicyError as err:
        console.print("[red]DatasetPolicyError[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=2) from None
    except ChecksumMismatch as err:
        console.print("[red]ChecksumMismatch[/red]\n")
        console.print(str(err), highlight=False)
        raise typer.Exit(code=3) from None
    for planned, path in zip(local.plan.files, local.paths, strict=True):
        verified = "checksum verified" if planned.sha256 else "no recorded checksum"
        console.print(f"{path}  [dim]({verified})[/dim]")
    console.print()
    console.print(local.attribution, highlight=False)
