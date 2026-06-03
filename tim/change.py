from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


@dataclass(frozen=True)
class Change:
    title: str
    desc: str | None
    shoulds: list[str]
    musts: list[str]
    approvals: list[str]
    branch: str | None
    log_path: Path

    def _format(self, title: str, steps: list[str]) -> str:
        if len(steps) == 0:
            return ""
        return title + "\n" + "\n".join(f"- {step}" for step in steps)

    def full_description(self) -> str:
        return dedent(
            f"""
            --- {self.title} ---
            {self.desc}

            {self._format("You SHOULD:", self.shoulds)}

            {self._format("You MUST:", self.musts)}

            {self._format("Your change is complete when:", self.approvals)}
            """
        ).strip()


class ChangeBuilder:
    def __init__(self, title: str):
        self._title = title
        self._desc = None
        self._shoulds: list[str] = []
        self._musts: list[str] = []
        self._approvals: list[str] = []
        self._branch = None
        self._log_path = None

    def desc(self, desc: str) -> "ChangeBuilder":
        self._desc = dedent(desc).strip()
        return self

    def shoulds(self, items: list[str]) -> "ChangeBuilder":
        self._shoulds = list(items)
        return self

    def musts(self, items: list[str]) -> "ChangeBuilder":
        self._musts = list(items)
        return self

    def approvals(self, items: list[str]) -> "ChangeBuilder":
        self._approvals = list(items)
        return self

    def branch(self, branch: str) -> "ChangeBuilder":
        self._branch = branch
        return self

    def log_path(self, log_path: Path) -> "ChangeBuilder":
        self._log_path = log_path
        return self

    def build(self) -> Change:
        return Change(
            title=self._title,
            desc=self._desc,
            shoulds=self._shoulds,
            musts=self._musts,
            approvals=self._approvals,
            branch=self._branch,
            log_path=self._log_path,
        )
