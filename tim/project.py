from datetime import datetime
from dataclasses import dataclass
import logging
import json
import os
from pathlib import Path
import subprocess

from tim.agentmessage import AgentMessage, AgentMessageSource, ToolCall


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


def _extract_role(message) -> str:
    if isinstance(message, dict):
        return message["role"]
    return message.role


def _extract_content(message) -> str:
    if isinstance(message, dict):
        return message["content"]
    return message.content


def _extract_tool_call_id(message) -> str:
    if isinstance(message, dict):
        return message["tool_call_id"]
    return message.tool_call_id


def _extract_duration(message) -> float:
    if isinstance(message, dict):
        return message["duration"]
    return message.duration


def _convert_tool_calls(raw_tool_calls):
    tool_calls = []
    for raw_call in raw_tool_calls:
        if isinstance(raw_call, dict):
            tool_calls.append(
                ToolCall(
                    id=raw_call["id"],
                    function_name=raw_call["function"]["name"],
                    arguments=raw_call["function"]["arguments"],
                )
            )
        else:
            tool_calls.append(
                ToolCall(
                    id=raw_call.id,
                    function_name=raw_call.function.name,
                    arguments=raw_call.function.arguments,
                )
            )
    return tool_calls


def _extract_reasoning(message):
    if isinstance(message, dict):
        return message.get("reasoning_content")
    return getattr(message, "reasoning_content", None)


def _extract_tool_calls_data(message):
    if isinstance(message, dict):
        return message.get("tool_calls")
    return getattr(message, "tool_calls", None)


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

    def _build_agent_message(
        self,
        agent_name: str,
        agent_instance: int,
        message,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        parent: AgentMessageSource | None = None,
    ) -> AgentMessage:
        message_role = _extract_role(message)

        match message_role:
            case "user":
                content = _extract_content(message)
                return AgentMessage.create_user(
                    agent=agent_name,
                    agent_instance=agent_instance,
                    content=content,
                    parent=parent,
                )
            case "system":
                content = _extract_content(message)
                return AgentMessage.create_system(
                    agent=agent_name,
                    agent_instance=agent_instance,
                    content=content,
                    parent=parent,
                )
            case "tool":
                tool_call_id = _extract_tool_call_id(message)
                content = _extract_content(message)
                return AgentMessage.create_tool(
                    agent=agent_name,
                    agent_instance=agent_instance,
                    tool_call_id=tool_call_id,
                    content=content,
                    duration=_extract_duration(message),
                    parent=parent,
                )
            case "assistant":
                content = _extract_content(message)
                reasoning = _extract_reasoning(message)
                raw_tool_calls = _extract_tool_calls_data(message)
                tool_calls = _convert_tool_calls(raw_tool_calls) if raw_tool_calls else []
                return AgentMessage.create_assistant(
                    agent=agent_name,
                    agent_instance=agent_instance,
                    content=content,
                    reasoning=reasoning,
                    tool_calls=tool_calls or None,
                    prompt_tokens=prompt_tokens or 0,
                    completion_tokens=completion_tokens or 0,
                    parent=parent,
                )
            case unknown_role:
                raise ValueError(f"Unknown message role: {unknown_role}")

    def _agent_source(self, agent) -> AgentMessageSource:
        parent = agent.parent
        return AgentMessageSource(
            agent=agent.__class__.__name__,
            agent_instance=id(agent),
            parent=self._agent_source(parent) if parent is not None else None,
        )

    def agent_log(self, agent, message, prompt_tokens: int | None = None, completion_tokens: int | None = None):
        source = self._agent_source(agent)

        agent_message = self._build_agent_message(
            agent_name=source.agent,
            agent_instance=source.agent_instance,
            message=message,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            parent=source.parent,
        )

        self._write_agent_log(agent_message.to_dict())


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
