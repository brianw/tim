from typing import Annotated

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown

from tim import Project, ChangeBuilder
from tim.agent import Agent
from tim.codechange import apply_code_change
from tim.tools import view_file, run, ls

_console = Console()


def _print_llm(text: str) -> None:
    if text is None:
        _console.print("None", style="red")
        return
    _console.print(Markdown(text), style="cyan")


CLI_PROMPT = """
You are assisting a software engineer, use the tools provided and your own knowledge to help
in any way you can.

The engineer may refer to existing code or system behavior. Use tools to understand the current
state if it will help the answer.

You MUST use the code_change tool when changing or adding project code.
- This tool ensures edits conform to coding standards and guidelines. Changes made without this tool will be rejected.
- You MUST give the code_change tool your full, researched plan.

Project root is: {root}
{listing}
""".strip()


def code_change(
    project: Project,
    title: Annotated[str, "A brief title for this change"],
    plan: Annotated[
        str, "Your detailed plan for this change, including approach to take, filenames to modify and commands to run"
    ],
    complete_when: Annotated[
        list[str],
        "How to validate this change, one or more shell commands to run that prove this change is complete and working correctly",
    ],
) -> str:
    """Required for all coding tasks: creating new files, editing existing code, fixing bugs, adding features."""
    change = (
        ChangeBuilder(title)
        .desc(plan)
        .shoulds(
            [
                "Use good, teutonic variable names",
                "No single letter variable names, outside of loop indexes or comprehensions",
                "Functions should be short, no larger than 20 lines",
                "Avoid duplicating code by extracting shared logic to reusable functions",
                "Minimise code inside an except block (extract to another function if neccessary)",
                "Follow the same patterns and conventions as the rest of the codebase",
            ]
        )
        .musts(
            [
                "Never silently swallow errors",
                "Avoid fallbacks like os.getenv('SOME_KEY', 'default-value'), fail early with os.environ['SOME_KEY']",
                "No docstrings or comments, the implementation must explain itself with good naming and composition",
                "No imports inside of functions",
            ]
        )
        .approvals(
            [
                "./lint passes",
                *complete_when,
            ]
        )
        .build()
    )
    print(f"*** Starting coding agent for: {title} ***")
    print(plan)
    print("\n\n\nComplete when:")
    for condition in complete_when:
        print(f" - {condition}")
    print()
    print("Coding agent response:")
    response = apply_code_change(project, change)
    _print_llm(response)
    print()
    return response


class CliAgent(Agent):
    def __init__(self, project: Project):
        prompt = CLI_PROMPT.format(
            root=project.run("pwd").stdout.strip(),
            listing=project.run("ls -la").stdout,
        )
        super().__init__(
            project=project,
            system_prompt=prompt,
            tools=[code_change, view_file, run, ls],
        )

    def run_forever(self):
        session = PromptSession()

        while True:
            user_message = ""
            while len(user_message) == 0:
                user_message = session.prompt("> ").strip()

            if user_message in ("/quit", "/q"):
                break

            elif user_message == "/think":
                self.enable_reasoning = True
                print("Thinking enabled")
                continue

            elif user_message == "/nothink":
                self.enable_reasoning = False
                print("Thinking disabled")
                continue

            self.add_user_message(user_message)
            _print_llm(self.start())
