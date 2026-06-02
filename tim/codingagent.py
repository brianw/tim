import logging

# from typing import Annotated
from .agent import Agent
from .project import Project, Change
from .tools import view_file, create_file, edit_file, ls, run


SYSTEM_PROMPT = """
You are an expert software engineer, writing confident idiomatic code using the tools provided.
Do not explain your code or summarise your changes.

Project root is: {root}
{listing}

Task:
{task}
"""

logger = logging.getLogger(__name__)


# def run_all_tests(change: Change) -> str:
#     """Run the full project test suite and return the output"""
#     result = change.run("pytest .", timeout=300)
#     if result.startswith("exit: 0\n"):
#         return "All tests passed"
#     return result


# def run_single_test(change: Change, test_path: Annotated[str, "pytest test reference"]) -> str:
#     """Run a single test, returning the output"""
#     return change.run(f"pytest {test_path}", timeout=300)


class CodingAgent(Agent):
    def __init__(self, project: Project, change: Change):
        prompt = SYSTEM_PROMPT.format(
            task=change.full_description(),
            root=project.run("pwd").stdout.strip(),
            listing=project.run("ls -la").stdout,
        )
        super().__init__(
            project=project,
            system_prompt=prompt,
            tools=[ls, view_file, create_file, edit_file, run],
        )
