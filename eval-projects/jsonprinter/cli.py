from __future__ import annotations

import logging

import click

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    level=logging.WARNING,
)


def _configure_logging(verbosity: int) -> None:
    logger = logging.getLogger()
    if verbosity >= 2:
        logger.setLevel(logging.DEBUG)
    elif verbosity >= 1:
        logger.setLevel(logging.INFO)


@click.group()
@click.option("-v", "--verbose", count=True, default=0, help="Increase verbosity (-v: INFO, -vv: DEBUG)")
@click.pass_context
def cli(context: click.Context, verbose: int) -> None:
    _configure_logging(verbosity=verbose)
    context.ensure_object(dict)
    context.obj["verbose"] = verbose


@cli.command()
@click.pass_context
def view(context: click.Context) -> None:
    click.echo("view")


@cli.command()
@click.pass_context
def reformat(context: click.Context) -> None:
    click.echo("reformat")


def _main() -> None:
    try:
        cli()
    except SystemExit:
        raise


if __name__ == "__main__":
    _main()
