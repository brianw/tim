import logging
from textwrap import dedent
from typing import Annotated

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown

from tim import Project, ChangeBuilder
from tim.agent import Agent
from tim.codechange import apply_code_change
from tim.tools import view_file, run, ls

_console = Console()
logger = logging.getLogger(__name__)

STYLE_STATUS = "yellow"
STYLE_LLM = "cyan"
STYLE_ERROR = "red"


def _print_llm(text: str) -> None:
    if text is None:
        _console.print("No final message from the LLM, this is likely a bug.", style=STYLE_ERROR)
        return
    _console.print(Markdown(text), style=STYLE_LLM)


def code_change(
    project: Project,
    parent_agent: Agent,
    title: Annotated[str, "A brief title for this change"],
    plan: Annotated[
        str,
        "Your detailed plan for this change, including approach to take, filenames to modify and commands to run. You MUST provide as much detail as possible.",
    ],
    files: Annotated[
        list[str],
        "The list of file paths that need to be examined or modified for this change.",
    ],
) -> str:
    """
    Required for all coding tasks: creating new files, editing existing code, fixing bugs, adding features.

    You MUST instruct this tool as you would a junior engineer.
    You MUST provide full details of the change along with your COMPLETE plan.
    """

    _console.print(f"*** Starting coding agent for: {title} ***", style=STYLE_STATUS)
    _console.print(Markdown(plan), style=STYLE_LLM)
    _console.print("\nFiles involved:", style=STYLE_STATUS)
    for file in files:
        _console.print(f" - {file}", style=STYLE_STATUS)
    _console.print("\nApproval steps:", style=STYLE_STATUS)

    complete_when = ApprovalConditionsAgent(project, f"--- {title} ---\n{plan}", parent=parent_agent).answer()
    change = (
        ChangeBuilder(title)
        .desc(f"{plan}\nFiles to examine/modify: {files}\n")
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
                "Avoid fallbacks and default values, fail early instead. E.g. when reading an environment variable always use os.environ['SOME_KEY'] rather than os.getenv('SOME_KEY', 'default-value')",
                "No docstrings or comments, the implementation must explain itself with good naming and composition -- except where required for tool definitions (e.g. tim/tools.py)",
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
    for condition in complete_when:
        _console.print(f" - {condition}", style=STYLE_LLM)
    print()
    _console.print("Coding agent response:", style=STYLE_STATUS)
    response = apply_code_change(project, change, parent_agent=parent_agent)
    _print_llm(response)
    print()
    return response


class CliAgent(Agent):
    PROMPT = dedent(
        """
        You are assisting a software engineer, use the tools provided and your own knowledge to help
        in any way you can.

        The engineer may refer to existing code or system behavior. Use tools to understand the current
        state if it will help the answer.

        You MUST use the code_change tool when changing or adding project code.
        - This tool ensures edits conform to coding standards and guidelines. Changes made without this tool will be rejected.
        - You MUST give the code_change tool your full, researched plan.

        Project root is: {root}
        {listing}
        """
    ).strip()

    def __init__(self, project: Project):
        prompt = self.PROMPT.format(
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
                _console.print("Thinking enabled", style=STYLE_STATUS)
                continue

            elif user_message == "/nothink":
                self.enable_reasoning = False
                _console.print("Thinking disabled", style=STYLE_STATUS)
                continue

            elif user_message == "/code":
                plan = self.messages[-1].content
                title = ExtractTitleAgent(project=self.project, plan=plan, parent=self).answer()
                response = code_change(self.project, self, title, plan, files=[])
                _print_llm(response)
                continue

            self.add_user_message(user_message)
            _print_llm(self.start())


class ApprovalConditionsAgent(Agent):
    PROMPT = dedent(
        """
        Act as an experienced, professional software engineer. A junior engineer on your team has been
        given the task below. They haven't started implementation yet.
        
        Your job is to write the commands to run that prove the change is complete and working correctly
        once they're done.

        You may examine the project using the tools provided to produce your list of validation commands.
        The validation commands should be specific to this functionality and validate as much as possible.
        
        Task:
        {task}

        Project root: {root}
        
        {format}
        """
    ).strip()

    ANSWER_FORMAT = (
        "You MUST respond with a valid JSON list, containing one or more shell command lines to validate the change."
    )

    def __init__(self, project: Project, task: str, **kwargs):
        super().__init__(
            project=project,
            system_prompt=self.PROMPT.format(
                task=task, root=project.run("pwd").stdout.strip(), format=self.ANSWER_FORMAT
            ),
            tools=[view_file, run, ls],
            enable_reasoning=True,
            **kwargs,
        )

    def answer_format_prompt(self) -> str:
        return self.ANSWER_FORMAT

    def validate_answer(self, answer) -> bool:
        return isinstance(answer, list)


class ExtractTitleAgent(Agent):
    PROMPT = "Create a one sentence title for this plan that captures the intent of the change:\n\n{plan}\n\n{format}"
    ANSWER_FORMAT = "You must return a valid JSON object in the format: {'title': <str containing title of change>}"

    def __init__(self, project, plan, **kwargs):
        super().__init__(
            project=project,
            system_prompt=self.PROMPT.format(format=self.ANSWER_FORMAT, plan=plan),
            tools=[],
            enable_reasoning=False,
            **kwargs,
        )

    def answer_format_prompt(self):
        return self.ANSWER_FORMAT

    def validate_answer(self, answer):
        return "title" in answer

    def format_answer(self, answer):
        return answer["title"].strip()
