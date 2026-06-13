import logging

import click

from tim.cliagent import CliAgent
from tim import MacSandboxProject


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
