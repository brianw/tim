from dataclasses import dataclass

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

Your final message must be a JSON response containing:
{{
    "reason": <a string containing the reason for your decision>,
    "result": <a bool, with true if the rule was followed completely, false otherwise>
}}
""".strip()


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


class PassFailAgent(Agent):
    def __init__(self, project: Project, change: Change, rule: str):
        self.rule = rule
        prompt = PASS_FAIL_PROMPT.format(
            task=f"{change.title}\n{change.desc}\n",
            root=project.run("pwd").stdout.strip(),
            rule=rule,
        )
        super().__init__(
            project=project,
            system_prompt=prompt,
            tools=[ls, view_file, run],
        )

    def answer(self) -> PassFailResult:
        response = self.extract_json(self.start())
        return PassFailResult(
            rule=self.rule,
            reason=response["reason"],
            answer=response["result"],
        )
