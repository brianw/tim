from dataclasses import dataclass
import logging
from pathlib import Path
import shlex
import subprocess
from textwrap import dedent


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Change:
    commit_message: str
    desc: str | None
    should: list[str]
    must: list[str]
    approval: list[str]
    branch: str | None

    def _format(self, title: str, steps: list[str]) -> str:
        if len(steps) == 0:
            return ""
        return title + "\n" + "\n".join(f"- {step}" for step in steps)

    def full_description(self) -> str:
        return dedent(
            f"""
            --- {self.commit_message} ---
            {self.desc}

            {self._format("You SHOULD:", self.should)}

            {self._format("You MUST:", self.must)}

            {self._format("Your change is complete when:", self.approval)}
            """
        ).strip()


class ChangeBuilder:
    def __init__(self, commit_message: str):
        self._commit_message = commit_message
        self._desc = None
        self._should: list[str] = []
        self._must: list[str] = []
        self._approval: list[str] = []
        self._branch = None

    def desc(self, desc: str) -> "ChangeBuilder":
        self._desc = dedent(desc).strip()
        return self

    def should(self, items: list[str]) -> "ChangeBuilder":
        self._should = list(items)
        return self

    def must(self, items: list[str]) -> "ChangeBuilder":
        self._must = list(items)
        return self

    def approval(self, items: list[str]) -> "ChangeBuilder":
        self._approval = list(items)
        return self

    def branch(self, branch: str) -> "ChangeBuilder":
        self._branch = branch
        return self

    def build(self) -> Change:
        return Change(
            commit_message=self._commit_message,
            desc=self._desc,
            should=self._should,
            must=self._must,
            approval=self._approval,
            branch=self._branch,
        )


@dataclass(frozen=True)
class RunOutput:
    returncode: int
    stdout: str
    stderr: str = ""
    exc: Exception | None = None

    @classmethod
    def timeout(cls, seconds: int):
        return cls(returncode=-1, stdout=f"Process timeout after {seconds} second(s)")

    def formatted(self) -> str:
        return f"<returncode>{self.returncode}</returncode>\n<stdout>{self.stdout}</stdout>\n<stderr>{self.stderr}</stderr>"


@dataclass(frozen=True)
class Project:
    root: Path

    @classmethod
    def cwd(cls) -> "Project":
        return cls(Path.cwd())

    def run(self, command: str, timeout: int = 1) -> RunOutput:
        raise NotImplementedError()

    def path(self, path: str | Path) -> Path:
        return Path(path).resolve()
    

class MacSandboxProject(Project):
    def run(self, command: str, timeout: int = 1) -> RunOutput:
        root = str(self.root.resolve())
        uv_cache = Path.home() / ".cache" / "uv"
        profile = "\n".join(
            [
                "(version 1)",
                "(allow default)",
                "(deny file-write*)",
                f'(allow file-write* (subpath "{root}"))',
                '(allow file-write* (literal "/dev/null"))',
                f'(allow file-write* (subpath "{uv_cache}"))',
                '(allow file-write* (subpath "/tmp"))',
                '(allow file-write* (subpath "/private/tmp"))',
            ]
        )
        exec_args = ["sandbox-exec", "-p", profile] + shlex.split(command)
        logger.debug(f"Running {command=} {timeout=}")
        try:
            result = subprocess.run(
                exec_args,
                cwd=self.root,
                capture_output=True,
                text=True,
                shell=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.debug(f"Command timeout: {command=} {timeout=}")
            return RunOutput.timeout(timeout)

        output = RunOutput(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        logger.debug(f"Command {command=} {timeout=} output={output!r}")
        return output
