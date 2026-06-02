import inspect
import json
import logging
from collections.abc import Callable
from functools import partial
from typing import Annotated, get_args, get_origin
from openai import OpenAI, BadRequestError
from pydantic import Field, create_model, validate_call
from .project import Project


ENDPOINT = "http://lab.dogg.ie:8080/v1"
MODEL = "local"
CONTEXT_WINDOW_SIZE = 131_072

logger = logging.getLogger(__name__)


class MaxToolCallsExceeded(RuntimeError): ...


class ContextWindowExceeded(RuntimeError): ...


def _tool_name(tool: Callable) -> str:
    return tool.__name__ if hasattr(tool, "__name__") else type(tool).__name__


def _tool_schema(tool: Callable) -> dict:
    fn = tool if inspect.isfunction(tool) or inspect.ismethod(tool) else tool.__call__
    sig = inspect.signature(fn)
    params = list(sig.parameters.items())

    if not params or params[0][0] != "project":
        raise TypeError(f"{_tool_name(tool)} must have 'project' as its first parameter")

    doc = inspect.getdoc(fn)
    if doc is None:
        raise TypeError(f"{_tool_name(tool)} must have a docstring")

    fields = {}
    for name, param in params[1:]:
        annotation = param.annotation
        if get_origin(annotation) is Annotated:
            base, desc = get_args(annotation)
            fields[name] = (base, Field(..., description=desc))
        else:
            fields[name] = (annotation, ...)
    model = create_model(_tool_name(tool), **fields)
    return {
        "type": "function",
        "function": {
            "name": _tool_name(tool),
            "description": doc,
            "parameters": model.model_json_schema(),
        },
    }


def api_client() -> OpenAI:
    return OpenAI(base_url=ENDPOINT, api_key="sk-no-key")


class Agent:
    def __init__(
        self,
        system_prompt: str,
        project: Project,
        tools: list[Callable],
        context_window_size: int = CONTEXT_WINDOW_SIZE,
    ):
        self.project = project
        self.context_window_size = context_window_size
        self.completion_fn = partial(
            api_client().chat.completions.create,
            model=MODEL,
            tools=[_tool_schema(tool) for tool in tools],
            parallel_tool_calls=False,
        )
        self.tools_by_name = {
            _tool_name(tool): validate_call(
                tool if inspect.isfunction(tool) or inspect.ismethod(tool) else tool.__call__
            )
            for tool in tools
        }
        self.messages = [{"role": "system", "content": system_prompt}]

    def before_tool_calls(self, tokens_used: int, tokens_available: int): ...

    def start(self, max_turns: int = 500) -> str:
        for turn in range(max_turns):
            response = self.complete()
            message = response.choices[0].message
            logger.debug(f"[{turn=}] LLM response: {message}")

            if not message.tool_calls:
                logger.debug(f"[{turn=}] No further tool calls, returning. Final response: {message.content}")
                return message.content

            self.before_tool_calls(
                tokens_used=response.usage.prompt_tokens + response.usage.completion_tokens,
                tokens_available=self.context_window_size,
            )

            for tool_call in message.tool_calls:
                logger.debug(f"[{turn=}] LLM requested tool: {tool_call.function.name}({tool_call.function.arguments})")

                tool_callable = self.tools_by_name[tool_call.function.name]
                result = tool_callable(self.project, **json.loads(tool_call.function.arguments))
                logger.debug(f"[{turn=}] Tool returned: {result}")

                tool_result = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
                self.messages.append(tool_result)

        raise MaxToolCallsExceeded(f"Failed to complete after {max_turns=} iterations")

    def complete(self):
        try:
            response = self.completion_fn(messages=self.messages)
        except BadRequestError as e:
            if e.type == "exceed_context_size_error":
                raise ContextWindowExceeded(e)
            raise

        tokens_used = response.usage.prompt_tokens + response.usage.completion_tokens
        if tokens_used > self.context_window_size:
            raise ContextWindowExceeded(f"{tokens_used=} but sf agent limited to {self.context_window_size}")

        message = response.choices[0].message
        self.messages.append(message)
        return response
