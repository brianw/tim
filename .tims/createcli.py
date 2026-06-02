from tim.project import MacSandboxProject, ChangeBuilder
from tim.applychange import apply_code_change

project = MacSandboxProject.cwd()
change = (
    ChangeBuilder("Add a tim CLI")
    .desc(
        """
        Create a new CLI in `tim/cli.py` using the click library.
        Add the click library to the project with uv.
        Configure the CLI as an executable tool in pyproject.toml, it should be called `tim`
        It should print "hello world" and nothing else.
        """
    )
    .should(
        [
            "Use good, teutonic variable names",
            "No single letter variable names, outside of loop indexes or comprehensions",
            "Functions should be short, no larger than 20 lines",
            "Avoid duplicating code by extracting shared logic to reusable functions",
        ]
    )
    .must(
        [
            "Never silently swallow errors",
            "Avoid fallbacks like os.getenv('SOME_KEY', 'default-value'), fail early with os.environ['SOME_KEY']",
            "No docstrings or comments, the implementation must explain itself with good naming and composition",
        ]
    )
    .approval(
        [
            "`uv run tim` shows the hello world message",
            "click is a project dependency in pyproject.toml",
        ]
    )
).build()

apply_code_change(project, change)
