import logging
from pathlib import Path

import click

from tim.cliagent import CliAgent
from tim import MacSandboxProject
from tim.logviewer import html_from_log


def _configure_logging(verbosity: int) -> None:
    if verbosity == 0:
        return
    log_level = logging.INFO
    if verbosity > 1:
        log_level = logging.DEBUG
    stream_handler = logging.StreamHandler()
    stream_handler.addFilter(lambda record: record.name.startswith("tim."))
    stream_handler.setLevel(log_level)
    logging.basicConfig(level=log_level, handlers=[stream_handler])


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", count=True, default=0)
def main(verbose: int) -> None:
    _configure_logging(verbose)
    ctx = click.get_current_context()

    if ctx.invoked_subcommand is None:
        project = MacSandboxProject.cwd()
        agent = CliAgent(project)
        agent.run_forever()


@main.command()
def run() -> None:
    print("run subcommand invoked")


@main.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
def log(log_file: str, output_path: str | None) -> None:
    log_path = Path(log_file)

    if output_path is None:
        output_path = str(log_path.with_suffix(".html"))

    html_content = html_from_log(log_file)
    Path(output_path).write_text(html_content, encoding="utf-8")
    click.echo(f"Wrote {output_path}")
