import logging
from pathlib import Path
from textwrap import dedent

from prompt_toolkit import PromptSession
from rich.console import Console
from rich.markdown import Markdown

from tim import Change, Project
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


class CliAgent(Agent):
    PROMPT = dedent(
        """
        You are assisting a software engineer, use the tools provided and your own knowledge to help
        in any way you can.

        The engineer may refer to existing code or system behavior. Use tools to understand the current
        state if it will help the answer.

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
            tools=[view_file, run, ls],
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

            elif user_message.startswith("/save "):
                filename = user_message.split()[1]
                self.save_change(filename)
                _console.print(f"Wrote {filename}", style=STYLE_STATUS)
                continue

            elif user_message.startswith("/run "):
                filename = user_message.split()[1]
                change = Change.from_yaml(Path(filename).read_text())
                _console.print(f"Applying {filename}", style=STYLE_STATUS)
                _print_llm(apply_code_change(project=self.project, change=change, parent_agent=self))
                continue

            elif user_message.startswith("/"):
                _console.print(f"Unknown command: {user_message}", style=STYLE_ERROR)
                continue

            self.add_user_message(user_message)
            _print_llm(self.start())

    def save_change(self, filename: str):
        plan = self.messages[-1].content
        change = ExtractChangeAgent(project=self.project, parent=self, plan=plan).answer()
        Path(filename).write_text(change.to_yaml())


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


class ExtractChangeAgent(Agent):
    PROMPT = dedent(
        """
        Convert the implementation plan below into a structured Change that another coding agent can
        execute without seeing the original conversation.

        Preserve the plan's intent, scope, filenames, technical details, and stated constraints. Do not
        invent requirements, implementation details, validation steps, or project conventions. Do not
        weaken mandatory language or promote a suggestion into a requirement.

        Populate the fields as follows:

        - title: A short, specific, action-oriented summary of the requested change.
        - desc: A self-contained description of what to change and how the plan says to approach it.
          Include relevant context, files, APIs, behavior, and edge cases. Exclude requirements already
          captured in shoulds or musts. Use null only when the plan contains no descriptive information.
        - shoulds: Explicit preferences, recommendations, or non-mandatory guidance. Write each as a
          standalone statement. Use an empty list when none are present.
        - musts: Explicit hard requirements, prohibitions, invariants, or acceptance criteria. Write each
          as a standalone statement. Use an empty list when none are present.
        - approvals: Explicit commands or checks used to prove the change works. Preserve shell commands
          exactly. Use an empty list when the plan gives no validation steps.

        Return only the requested JSON object. Do not include Markdown fences or explanatory text.

        Implementation plan:
        <plan>
        {plan}
        </plan>

        {format}
        """
    ).strip()
    ANSWER_FORMAT = dedent(
        """
        You MUST respond with a valid JSON object in this exact format:
        {
            "title": <string>,
            "desc": <string or null>,
            "shoulds": <list of strings>,
            "musts": <list of strings>,
            "approvals": <list of strings>
        }
        """
    ).strip()

    def __init__(self, project: Project, parent: Agent, plan: str):
        super().__init__(
            project=project,
            parent=parent,
            system_prompt=self.PROMPT.format(format=self.ANSWER_FORMAT, plan=plan),
            tools=[],
            enable_reasoning=False,
        )

    def answer_format_prompt(self):
        return self.ANSWER_FORMAT

    def validate_answer(self, answer) -> bool:
        if not isinstance(answer, dict):
            return False

        if set(answer) != {"title", "desc", "shoulds", "musts", "approvals"}:
            return False

        list_fields = ("shoulds", "musts", "approvals")
        return (
            isinstance(answer["title"], str)
            and (answer["desc"] is None or isinstance(answer["desc"], str))
            and all(isinstance(answer[field], list) for field in list_fields)
            and all(isinstance(item, str) for item in answer["shoulds"])
            and all(isinstance(item, str) for item in answer["musts"])
            and all(isinstance(item, str) for item in answer["approvals"])
        )

    def format_answer(self, answer) -> Change:
        return Change(**answer)
