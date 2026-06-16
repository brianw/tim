from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

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


def _read_source(input_path: Path | None) -> str:
    if input_path is not None:
        return input_path.read_text(encoding="utf-8")
    return sys.stdin.read()


def _write_output(output_path: Path | None, content: str) -> None:
    if output_path is not None:
        output_path.write_text(content, encoding="utf-8")
    else:
        click.echo(content)


@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False), default=None, required=False)
@click.option("-i", "--indent", type=int, default=4, help="Number of spaces for indentation")
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None, required=False)
@click.pass_context
def reformat(context: click.Context, path: Path | None, indent: int, output: Path | None) -> None:
    source = _read_source(Path(path) if path else None)
    parsed = json.loads(source)
    formatted = json.dumps(parsed, indent=indent, ensure_ascii=False) + "\n"
    _write_output(Path(output) if output else None, formatted)


if __name__ == "__main__":
    cli()
