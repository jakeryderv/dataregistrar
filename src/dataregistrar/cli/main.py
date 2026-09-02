import typer

import dataregistrar

app = typer.Typer(
    name="dreg",
    help="Discover, evaluate, and retrieve public data across providers.",
    no_args_is_help=True,
    add_completion=False,
)


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
