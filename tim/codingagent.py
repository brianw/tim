from dataclasses import dataclass
from textwrap import dedent
import logging

from tim import Project, Change
from tim.agent import Agent
from tim.tools import all_tools, view_file, ls, run


logger = logging.getLogger(__name__)


def format_change(change: Change) -> str:
    def format_steps(title: str, steps: list[str]) -> str:
        if not steps:
            return ""
        return title + "\n" + "\n".join(f"- {step}" for step in steps)

    return dedent(
        f"""
        --- {change.title} ---
        {change.desc}

        {format_steps("You SHOULD:", change.shoulds)}

        {format_steps("You MUST:", change.musts)}
        """
    ).strip()


class CodingAgent(Agent):
    PROMPT = dedent(
        """
        You are an expert software engineer, writing confident idiomatic code using the tools provided.
        Do not explain your code or summarise your changes.
        
        Project root is: {root}
        {listing}

        {task}
        """
    ).strip()

    def __init__(self, project: Project, change: Change, **kwargs):
        prompt = self.PROMPT.format(
            task=format_change(change),
            root=project.run("pwd").stdout.strip(),
            listing=project.run("ls -la").stdout,
        )
        super().__init__(project=project, system_prompt=prompt, tools=all_tools, **kwargs)


@dataclass(frozen=True)
class PassFailResult:
    rule: str
    reason: str
    answer: bool


class PassFailAgent(Agent):
    PROMPT = dedent(
        """
        You are an expert software engineer, reviewing a project change using the tools provided.

        The rule you are evaluating is: {rule}

        Do NOT create or modify files.
        Do NOT attempt to fix any problems you identify.
        Evaluate ONLY against changed files. You do not need to evaluate the entire project.
        Run source control tools to identify:
        - changes to existing files
        - newly added files

        DO NOT examine previous commits, only active unstaged changes.

        Project root is: {root}

        {format}
        """
    ).strip()

    PASS_FAIL_FORMAT = dedent(
        """
        Your final message must be a JSON response containing:
        {
            "reason": <a string containing the reason for your decision>,
            "result": <a bool, with true if the rule was followed completely, false otherwise>
        }
        """
    ).strip()

    def __init__(self, project: Project, rule: str, **kwargs):
        self.rule = rule
        prompt = self.PROMPT.format(
            root=project.run("pwd").stdout.strip(),
            rule=rule,
            format=self.PASS_FAIL_FORMAT,
        )
        super().__init__(project=project, system_prompt=prompt, tools=[ls, view_file, run], **kwargs)

    def answer_format_prompt(self) -> str:
        return self.PASS_FAIL_FORMAT

    def validate_answer(self, answer: dict) -> bool:
        return "reason" in answer and "result" in answer

    def format_answer(self, answer: dict) -> PassFailResult:
        return PassFailResult(
            rule=self.rule,
            reason=answer["reason"],
            answer=answer["result"],
        )
