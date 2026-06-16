import inspect
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from time import perf_counter
from typing import Annotated, get_args, get_origin, Optional
from openai import OpenAI, BadRequestError
from pydantic import Field, create_model
from tim import Project


ENDPOINT = "http://lab.dogg.ie:8080/v1"
MODEL = "local"
CONTEXT_WINDOW_SIZE = 131_072
ESTIMATED_CHARACTERS_PER_TOKEN = 2.5
MAX_TOOL_RESULT_TOKENS = CONTEXT_WINDOW_SIZE * 0.2


logger = logging.getLogger(__name__)


class MaxToolCallsExceeded(RuntimeError): ...


class ContextWindowExceeded(RuntimeError): ...


class MaxAnswerAttempsExceeded(Exception): ...


@dataclass(frozen=True)
class ToolCall:
    function_name: str
    arguments: dict
    result: str


def _tool_name(tool: Callable) -> str:
    return tool.__name__ if hasattr(tool, "__name__") else type(tool).__name__


def _tool_fn(tool: Callable) -> Callable:
    return tool if inspect.isfunction(tool) or inspect.ismethod(tool) else tool.__call__


def _annotated_fields(fn: Callable) -> dict:
    fields = {}
    for name, param in inspect.signature(fn).parameters.items():
        if get_origin(param.annotation) is Annotated:
            base, desc = get_args(param.annotation)
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[name] = (base, Field(default, description=desc))
    return fields


def _injected_names(fn: Callable) -> tuple[str, ...]:
    return tuple(
        name
        for name, param in inspect.signature(fn).parameters.items()
        if get_origin(param.annotation) is not Annotated
    )


class Tool:
    def __init__(self, tool: Callable):
        self.name = _tool_name(tool)
        self.fn = _tool_fn(tool)
        doc = inspect.getdoc(self.fn)
        if doc is None:
            raise TypeError(f"{self.name} must have a docstring")
        self.description = doc
        self.arguments = create_model(self.name, **_annotated_fields(self.fn))
        self.injected_names = _injected_names(self.fn)

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }

    def call(self, injectables: dict, arguments: dict) -> str:
        validated = self.arguments(**arguments)
        injected = {name: injectables[name] for name in self.injected_names if name in injectables}
        return self.fn(**injected, **validated.model_dump())


def api_client() -> OpenAI:
    return OpenAI(base_url=ENDPOINT, api_key="sk-no-key")


class Agent:
    def __init__(
        self,
        system_prompt: str,
        project: Project,
        tools: list[Callable],
        context_window_size: int = CONTEXT_WINDOW_SIZE,
        enable_reasoning: bool = True,
        parent: Optional["Agent"] = None,
    ):
        self.project = project
        self.context_window_size = context_window_size
        wrapped_tools = [Tool(tool) for tool in tools]
        self.completion_fn = partial(
            api_client().chat.completions.create,
            model=MODEL,
            tools=[tool.schema for tool in wrapped_tools],
            parallel_tool_calls=False,
        )
        self.tools_by_name = {tool.name: tool for tool in wrapped_tools}
        self.injectables = {"project": project, "parent_agent": self}
        self.messages = [{"role": "system", "content": system_prompt}]
        self.enable_reasoning = enable_reasoning
        self.parent = parent
        self.log_message(self.messages[0])

        self.tool_calls: list[ToolCall] = []
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0

    def log_message(self, message, prompt_tokens=None, completion_tokens=None):
        self.project.agent_log(self, message, prompt_tokens, completion_tokens)

    def start(self, max_turns: int = 500) -> str:
        for turn in range(max_turns):
            response = self.complete()
            message = response.choices[0].message
            logger.debug(f"[{turn=}] LLM response: {message}")

            self.prompt_tokens = response.usage.prompt_tokens
            self.completion_tokens = response.usage.completion_tokens

            if not message.tool_calls:
                logger.debug(f"[{turn=}] No further tool calls, returning. Final response: {message.content}")
                return message.content

            for tool_call in message.tool_calls:
                logger.debug(f"[{turn=}] LLM requested tool: {tool_call.function.name}({tool_call.function.arguments})")

                tool = self.tools_by_name[tool_call.function.name]
                started_at = perf_counter()
                result = tool.call(self.injectables, json.loads(tool_call.function.arguments))
                duration = perf_counter() - started_at
                logger.debug(f"[{turn=}] Tool returned: {result}")

                estimated_tokens = len(result) / ESTIMATED_CHARACTERS_PER_TOKEN
                if estimated_tokens > MAX_TOOL_RESULT_TOKENS:
                    logger.debug(
                        f"[{turn=}] Tool response exceeded {MAX_TOOL_RESULT_TOKENS=} ({estimated_tokens=}, len(result)={len(result)}), asking LLM to be more precise"
                    )
                    result = f"Tool use error: the tool returned a response containing {len(result)} characters, too large for this conversation. Please refine your operation."

                self.add_tool_response(tool_call, result, duration)

        raise MaxToolCallsExceeded(f"Failed to complete after {max_turns=} iterations")

    def add_user_message(self, content: str):
        message = {"role": "user", "content": content}
        self.messages.append(message)
        self.log_message(message)

    def add_tool_response(self, tool_call, result: str, duration: float):
        message = {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
            "duration": duration,
        }
        self.messages.append(message)
        self.log_message(message)
        self.tool_calls.append(
            ToolCall(
                function_name=tool_call.function.name,
                arguments=tool_call.function.arguments,
                result=result,
            )
        )

    def complete(self):
        try:
            response = self.completion_fn(
                messages=self.messages,
                extra_body={
                    "chat_template_kwargs": {
                        "enable_thinking": self.enable_reasoning,
                        "preserve_thinking": True,
                    }
                },
            )
        except BadRequestError as e:
            if e.type == "exceed_context_size_error":
                raise ContextWindowExceeded(e)
            raise

        tokens_used = response.usage.prompt_tokens + response.usage.completion_tokens
        if tokens_used > self.context_window_size:
            raise ContextWindowExceeded(f"{tokens_used=} but tim agent limited to {self.context_window_size}")

        message = response.choices[0].message
        self.messages.append(message)
        self.log_message(
            message, prompt_tokens=response.usage.prompt_tokens, completion_tokens=response.usage.completion_tokens
        )
        return response

    def extract_json(self, message: str):
        lines = message.splitlines()
        if "```json" not in lines:
            return json.loads(message)

        start_index = lines.index("```json") + 1
        end_index = lines.index("```", start_index)
        json_text = "\n".join(lines[start_index:end_index])
        return json.loads(json_text)

    def answer_format_prompt(self) -> str:
        return ""

    def validate_answer(self, answer: dict) -> str:
        return True

    def format_answer(self, answer: dict):
        return answer

    def answer(self, max_attempts: int = 5):
        for attempt in range(max_attempts):
            logger.info(f"[{attempt=}] Prompting for answer")
            try:
                response = self.extract_json(self.start())
            except json.decoder.JSONDecodeError as e:
                logger.info(f"[{attempt=}] Malformed response: {e!r}")
                self.add_user_message(f"Your last message was unparseable: {e}\n{self.answer_format_prompt()}")
                continue

            if not self.validate_answer(response):
                logger.info(f"[{attempt=}] Answer validation failed: {response}")
                self.add_user_message(
                    f"Your last message did not match the required format. Please correct.\n{self.answer_format_prompt()}"
                )
                continue

            logger.info(f"[{attempt=}] Answered")
            return self.format_answer(response)

        raise MaxAnswerAttempsExceeded(f"Failed to get a valid response after {max_attempts=}")
