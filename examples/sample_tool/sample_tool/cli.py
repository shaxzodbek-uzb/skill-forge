"""Click CLI for the sample greeter tool."""

import click

from . import farewell, greet


@click.group()
def cli() -> None:
    """Greet and bid farewell."""


@cli.command()
@click.argument("name")
def hello(name: str) -> None:
    """Print a greeting."""
    click.echo(greet(name))


@cli.command("bye")
@click.argument("name")
def bye(name: str) -> None:
    """Print a farewell."""
    click.echo(farewell(name))


def main() -> None:
    cli()
