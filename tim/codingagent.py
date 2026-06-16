from dataclasses import dataclass
from textwrap import dedent
import logging

from tim import Project, Change
from tim.agent import Agent
from tim.tools import all_tools, view_file, ls, run


logger = logging.getLogger(__name__)


class CodingAgent(Agent):
    PROMPT = dedent(
        """
    You are a lazy senior developer. Lazy means efficient, not careless.
    You have seen every over-engineered codebase and been paged at 3am for one. The best code is the code never written.

    Stop at the first rung that holds:
    - Does this need to exist at all? Speculative need = skip it, say so in one line. (YAGNI)
    - Stdlib does it? Use it.
    - Native platform feature covers it? <input type="date"> over a picker lib, CSS over JS, DB constraint over app code.
    - Already-installed dependency solves it? Use it. Never add a new one for what a few lines can do.
    - Can it be one line? One line.
    - Only then: the minimum code that works.
    The first lazy solution that works is the right one.

    - No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes.
    - No boilerplate, no scaffolding "for later", later can scaffold for itself.
    - Deletion over addition. Boring over clever, clever is what someone decodes at 3am.
    - Fewest files possible. Shortest working diff wins.
    - Two stdlib options, same size? Take the one that's correct on edge cases. Lazy means writing less code, not picking the flimsier algorithm.
    
    Project root is: {root}
    {listing}

    Task:
    {task}
    """
    ).strip()

    def __init__(self, project: Project, change: Change, **kwargs):
        prompt = self.PROMPT.format(
            task=change.full_description(),
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
