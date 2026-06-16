from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


__all__ = [
    "AgentMessage",
    "AgentMessageSource",
    "AgentMessageUsage",
    "AssistantMessage",
    "ToolCall",
    "ToolMessage",
    "UserMessage",
    "SystemMessage",
]


@dataclass(frozen=True)
class ToolCall:
    id: str
    function_name: str
    arguments: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.function_name,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCall:
        return cls(
            id=data["id"],
            function_name=data["name"],
            arguments=data["arguments"],
        )


@dataclass(frozen=True)
class AgentMessageSource:
    agent: str
    agent_instance: int
    parent: AgentMessageSource | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "agent": self.agent,
            "agent_instance": self.agent_instance,
        }
        if self.parent is not None:
            result["parent"] = self.parent.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessageSource:
        parent = cls.from_dict(data["parent"]) if data.get("parent") else None
        return cls(
            agent=data["agent"],
            agent_instance=data["agent_instance"],
            parent=parent,
        )


@dataclass(frozen=True)
class AgentMessageUsage:
    prompt_tokens: int
    completion_tokens: int

    @classmethod
    def empty(cls) -> AgentMessageUsage:
        return cls(prompt_tokens=0, completion_tokens=0)

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessageUsage:
        return cls(
            prompt_tokens=data["prompt_tokens"],
            completion_tokens=data["completion_tokens"],
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _BaseMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    @classmethod
    def model_validate_dict(cls, data: dict[str, Any]) -> _BaseMessage:
        message_type = data["role"]
        type_map: dict[str, type[_BaseMessage]] = {
            "user": UserMessage,
            "system": SystemMessage,
            "assistant": AssistantMessage,
            "tool": ToolMessage,
        }
        target = type_map[message_type]
        return target.model_validate(data)


class UserMessage(_BaseMessage):
    role: Literal["user"] = "user"
    content: str

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}


class SystemMessage(_BaseMessage):
    role: Literal["system"] = "system"
    content: str

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}


class AssistantMessage(_BaseMessage):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    reasoning: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @field_validator("tool_calls", mode="before")
    @classmethod
    def _parse_tool_calls(cls, value: Any) -> list[ToolCall]:
        if isinstance(value, list):
            return [ToolCall.from_dict(call) if isinstance(call, dict) else call for call in value]
        return value

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.reasoning is not None:
            result["reasoning"] = self.reasoning
        if self.tool_calls:
            result["tool_calls"] = [call.to_dict() for call in self.tool_calls]
        return result


class ToolMessage(_BaseMessage):
    role: Literal["tool"] = "tool"
    tool_call_id: str = Field(alias="id")
    content: str
    duration: float

    @field_validator("tool_call_id", mode="before")
    @classmethod
    def _resolve_id(cls, value: Any) -> str:
        if isinstance(value, dict):
            return value.get("tool_call_id", value.get("id", ""))
        return str(value)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "role": self.role,
            "id": self.tool_call_id,
            "content": self.content,
            "duration": self.duration,
        }


@dataclass(frozen=True)
class AgentMessage:
    source: AgentMessageSource
    timestamp: str
    message: _BaseMessage
    usage: AgentMessageUsage = field(default_factory=AgentMessageUsage.empty)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source": self.source.to_dict(),
            "at": self.timestamp,
            "message": self.message.model_dump(),
        }
        if self.usage.prompt_tokens > 0 or self.usage.completion_tokens > 0:
            result["usage"] = self.usage.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        source = AgentMessageSource.from_dict(data["source"])
        message = _BaseMessage.model_validate_dict(data["message"])
        usage = AgentMessageUsage.empty()
        if "usage" in data:
            usage = AgentMessageUsage.from_dict(data["usage"])
        return cls(
            source=source,
            timestamp=data["at"],
            message=message,
            usage=usage,
        )

    @classmethod
    def create_user(
        cls, agent: str, agent_instance: int, content: str, parent: AgentMessageSource | None = None
    ) -> AgentMessage:
        return cls(
            source=AgentMessageSource(agent=agent, agent_instance=agent_instance, parent=parent),
            timestamp=_utc_now_iso(),
            message=UserMessage(content=content),
        )

    @classmethod
    def create_system(
        cls, agent: str, agent_instance: int, content: str, parent: AgentMessageSource | None = None
    ) -> AgentMessage:
        return cls(
            source=AgentMessageSource(agent=agent, agent_instance=agent_instance, parent=parent),
            timestamp=_utc_now_iso(),
            message=SystemMessage(content=content),
        )

    @classmethod
    def create_assistant(
        cls,
        agent: str,
        agent_instance: int,
        content: str | None = None,
        reasoning: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        parent: AgentMessageSource | None = None,
    ) -> AgentMessage:
        return cls(
            source=AgentMessageSource(agent=agent, agent_instance=agent_instance, parent=parent),
            timestamp=_utc_now_iso(),
            message=AssistantMessage(
                content=content,
                reasoning=reasoning,
                tool_calls=tool_calls or [],
            ),
            usage=AgentMessageUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    @classmethod
    def create_tool(
        cls,
        agent: str,
        agent_instance: int,
        tool_call_id: str,
        content: str,
        duration: float,
        parent: AgentMessageSource | None = None,
    ) -> AgentMessage:
        return cls(
            source=AgentMessageSource(agent=agent, agent_instance=agent_instance, parent=parent),
            timestamp=_utc_now_iso(),
            message=ToolMessage(id=tool_call_id, content=content, duration=duration),
        )
