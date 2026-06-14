from dataclasses import dataclass
import json
import logging

from tim import Project, Change
from tim.agent import Agent
from tim.tools import all_tools, view_file, ls, run


CODING_PROMPT = """
You are an expert software engineer, writing confident idiomatic code using the tools provided.
Do not explain your code or summarise your changes.

Project root is: {root}
{listing}

Task:
{task}
""".strip()


PASS_FAIL_PROMPT = """
You are an expert software engineer, reviewing a project change using the tools provided.

The rule you are evaluating is: {rule}

Do NOT create or modify files.
Do NOT attempt to fix any problems you identify.
Evaluate ONLY against changed files. You do not need to evaluate the entire project.
Run source control tools to identify local changes.

Project root is: {root}

The change you are reviewing must:
{task}

{format}
""".strip()

PASS_FAIL_FORMAT = """
Your final message must be a JSON response containing:
{{
    "reason": <a string containing the reason for your decision>,
    "result": <a bool, with true if the rule was followed completely, false otherwise>
}}
""".strip()


logger = logging.getLogger(__name__)


class CodingAgent(Agent):
    def __init__(self, project: Project, change: Change):
        prompt = CODING_PROMPT.format(
            task=change.full_description(),
            root=project.run("pwd").stdout.strip(),
            listing=project.run("ls -la").stdout,
        )
        super().__init__(
            project=project,
            system_prompt=prompt,
            tools=all_tools,
        )


@dataclass(frozen=True)
class PassFailResult:
    rule: str
    reason: str
    answer: bool


class MaxAnswerAttempsExceeded(Exception): ...


class PassFailAgent(Agent):
    def __init__(self, project: Project, change: Change, rule: str):
        self.rule = rule
        prompt = PASS_FAIL_PROMPT.format(
            task=f"{change.title}\n{change.desc}\n",
            root=project.run("pwd").stdout.strip(),
            rule=rule,
            format=PASS_FAIL_FORMAT,
        )
        super().__init__(
            project=project,
            system_prompt=prompt,
            tools=[ls, view_file, run],
        )

    def answer(self, max_attempts: int = 5) -> PassFailResult:
        for attempt in range(max_attempts):
            logger.info(f"[{attempt=}] Attempting to answer: {self.rule}")
            try:
                response = self.extract_json(self.start())
            except json.decoder.JSONDecodeError as e:
                logger.info(f"[{attempt=}] Malformed response: {e!r}")
                self.add_user_message(PASS_FAIL_FORMAT)
                continue

            if "reason" not in response or "result" not in response:
                logger.info(f"[{attempt=}] Missing expected fields in response: {response}")
                self.add_user_message(PASS_FAIL_FORMAT)
                continue

            logger.info(f"[{attempt=}] {self.rule} ? {response['result']}")
            return PassFailResult(
                rule=self.rule,
                reason=response["reason"],
                answer=response["result"],
            )
        raise MaxAnswerAttempsExceeded(f"Failed to get a valid response after {max_attempts=}")
