from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess


logger = logging.getLogger(__name__)


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
        return (self.root / path).resolve()


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
        exec_args = ["sandbox-exec", "-p", profile, "sh", "-c", command]
        logger.debug(f"Running {command=} {timeout=}")
        try:
            result = subprocess.run(
                exec_args,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.debug(f"Command timeout: {command=} {timeout=}")
            return RunOutput.timeout(timeout)

        output = RunOutput(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        logger.debug(f"Command {command=} {timeout=} output={output!r}")
        return output
