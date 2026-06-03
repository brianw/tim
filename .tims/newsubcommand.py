import logging
from tim import MacSandboxProject, ChangeBuilder
from tim.codechange import apply_code_change

_handler = logging.StreamHandler()
_handler.addFilter(lambda r: r.name.startswith("tim."))
logging.basicConfig(level=logging.DEBUG, handlers=[_handler])


project = MacSandboxProject.cwd()
change = (
    ChangeBuilder("Add a `new` subcommand to the CLI")
    .desc(
        """
        Update the CLI in `tim/cli.py` to add a new subcommand: `new`
        It should take one positional argument, `title`, which is the title of the change
        Add a verbose flag at the top-level click parser, so `-v` or `--verbose` enables info level logging:
            - copy the logging config from .tims/newsubcommand.py, including the filter for logger names starting with `tim.`
            - -v should enable info level logging to stdout
            - -vv should enable debug level logging to stdout
        Update the main click handler that currently prints "hello world" to include 2 log messages:
            - at INFO level: "this is an info log message"
            - at DEBUG level: "this is a debug log message"
        """
    )
    .shoulds(
        [
            "Use good, teutonic variable names",
            "No single letter variable names, outside of loop indexes or comprehensions",
            "Functions should be short, no larger than 20 lines",
            "Avoid duplicating code by extracting shared logic to reusable functions",
        ]
    )
    .musts(
        [
            "Never silently swallow errors",
            "Avoid fallbacks like os.getenv('SOME_KEY', 'default-value'), fail early with os.environ['SOME_KEY']",
            "No docstrings or comments, the implementation must explain itself with good naming and composition",
        ]
    )
    .approvals(
        [
            "`uv run tim new` fails with a missing `title` argument error",
            "`uv run tim new some-title` exits without an error",
            "`uv run tim -v` prints the hello world text along with `this is an info log message` and not the `this is a debug log message`",
            "`uv run tim -vv` prints the hello world text and both log messages",
        ]
    )
).build()

apply_code_change(project, change)
