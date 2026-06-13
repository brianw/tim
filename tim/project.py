from datetime import datetime, timezone
from dataclasses import dataclass
import logging
import json
import os
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

    def __post_init__(self) -> None:
        timestamp = datetime.now().isoformat().replace(":", "-")
        self.agent_log_path = self.root / ".tim" / "agent-logs" / f"{timestamp}-{os.getpid()}.jsonl"

    @classmethod
    def cwd(cls) -> "Project":
        return cls(Path.cwd())

    def run(self, command: str, timeout: int = 1) -> RunOutput:
        raise NotImplementedError()

    def path(self, path: str | Path) -> Path:
        return (self.root / path).resolve()

    def _write_agent_log(self, logline: dict):
        self.agent_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.agent_log_path, "a", encoding="utf-8") as out:
            out.write(json.dumps(logline))
            out.write("\n")

    def agent_log(self, agent, message, prompt_tokens=None, completion_tokens=None):
        logline = {
            "source": {
                "agent": agent.__class__.__name__,
                "agent_instance": id(agent),
            },
            "at": datetime.now(timezone.utc).isoformat(),
            "message": _format_message(message),
        }
        if prompt_tokens is not None or completion_tokens is not None:
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
            logline["usage"] = usage
        self._write_agent_log(logline)


def _format_user_message(message) -> dict:
    return {
        "role": "user",
        "content": message["content"],
    }


def _format_system_message(message) -> dict:
    return {
        "role": "system",
        "content": message["content"],
    }


def _format_assistant_message(message) -> dict:
    tool_calls = []
    if message.tool_calls is not None:
        tool_calls = message.tool_calls
    reasoning_content = None
    if hasattr(message, "reasoning_content"):
        reasoning_content = message.reasoning_content
    return {
        "role": "assistant",
        "content": message.content,
        "reasoning": reasoning_content,
        "tool_calls": [
            {"id": tool.id, "name": tool.function.name, "arguments": tool.function.arguments} for tool in tool_calls
        ],
    }


def _format_tool_message(message) -> dict:
    return {
        "role": "tool",
        "id": message["tool_call_id"],
        "content": message["content"],
    }


def _format_message(message) -> dict:
    if isinstance(message, dict):
        role = message["role"]
    else:
        role = message.role
    return {
        "user": _format_user_message,
        "assistant": _format_assistant_message,
        "tool": _format_tool_message,
        "system": _format_system_message,
    }[role](message)


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
