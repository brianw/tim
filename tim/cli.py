import logging

import click


_logger = logging.getLogger(__name__)


def _configure_logging(verbosity: int) -> None:
    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(lambda record: record.name.startswith("tim."))
    if verbosity == 0:
        return
    log_level = logging.INFO if verbosity == 1 else logging.DEBUG
    stream_handler.setLevel(log_level)
    logging.basicConfig(level=log_level, handlers=[stream_handler])


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", count=True, default=0)
def main(verbose: int) -> None:
    _configure_logging(verbose)
    _logger.info("this is an info log message")
    _logger.debug("this is a debug log message")
    click.echo("hello world")


@main.command()
@click.argument("title")
def new(title: str) -> None:
    click.echo(title)
