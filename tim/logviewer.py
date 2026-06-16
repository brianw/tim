import html
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tim.agentmessage import AgentMessage, AssistantMessage


_AGENT_COLORS: list[str] = [
    "#4f8cff",
    "#ff7f4e",
    "#33b56a",
    "#b06bff",
    "#e6478c",
    "#f5a623",
    "#16b3b3",
    "#d64545",
    "#7a8cff",
    "#5fb84a",
    "#c97b1f",
    "#9b59b6",
    "#2c9faf",
    "#e0529c",
    "#6fae3a",
    "#b8743f",
]


def _agent_color(index: int) -> str:
    return _AGENT_COLORS[index % len(_AGENT_COLORS)]


def _parse_timestamp(timestamp_string: str) -> datetime:
    return datetime.fromisoformat(timestamp_string)


def _format_clock(timestamp: datetime) -> str:
    return timestamp.strftime("%H:%M:%S.%f")[:-3]


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remaining_seconds = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:02d}s"
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes:02d}m"


def _format_tokens(prompt_tokens: int, completion_tokens: int) -> str:
    if not prompt_tokens and not completion_tokens:
        return ""
    return f"{prompt_tokens + completion_tokens:,} tok"


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except json.JSONDecodeError:
        return text


def _summarise_value(value: object) -> str:
    if isinstance(value, str) and "\n" in value:
        return "..."
    return json.dumps(value)


def _format_params(arguments: str) -> str:
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return ", ".join(f"{key}={_summarise_value(value)}" for key, value in parsed.items())


@dataclass
class ToolInvocation:
    call_id: str
    name: str
    arguments: str
    agent_instance: int
    request_index: int
    start: datetime
    end: datetime | None = None
    response_index: int | None = None
    duration: float | None = None


@dataclass
class AgentInfo:
    instance: int
    name: str
    parent_instance: int | None
    seq: int
    color: str
    indices: list[int] = field(default_factory=list)
    tool_calls: list[ToolInvocation] = field(default_factory=list)
    first: datetime | None = None
    last: datetime | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def duration(self) -> float:
        return (self.last - self.first).total_seconds()


@dataclass
class LogModel:
    entries: list[AgentMessage]
    agents: dict[int, AgentInfo]
    tools_by_id: dict[str, ToolInvocation]
    roots: list[int]
    call_children: dict[str, list[int]]
    direct_children: dict[int, list[int]]
    step_durations: dict[int, float]


def _build_agents(entries: list[AgentMessage]) -> tuple[dict[int, AgentInfo], dict[str, ToolInvocation]]:
    agents: dict[int, AgentInfo] = {}
    tools_by_id: dict[str, ToolInvocation] = {}

    for index, entry in enumerate(entries):
        source = entry.source
        instance = source.agent_instance
        timestamp = _parse_timestamp(entry.timestamp)

        agent = agents.get(instance)
        if agent is None:
            agent = AgentInfo(
                instance=instance,
                name=source.agent,
                parent_instance=source.parent.agent_instance if source.parent else None,
                seq=len(agents) + 1,
                color=_agent_color(len(agents)),
                first=timestamp,
            )
            agents[instance] = agent

        agent.indices.append(index)
        agent.last = timestamp
        agent.prompt_tokens += entry.usage.prompt_tokens
        agent.completion_tokens += entry.usage.completion_tokens

        if isinstance(entry.message, AssistantMessage):
            for tool_call in entry.message.tool_calls:
                invocation = ToolInvocation(
                    call_id=tool_call.id,
                    name=tool_call.function_name,
                    arguments=tool_call.arguments,
                    agent_instance=instance,
                    request_index=index,
                    start=timestamp,
                )
                agent.tool_calls.append(invocation)
                tools_by_id[tool_call.id] = invocation

        if entry.message.role == "tool":
            invocation = tools_by_id.get(entry.message.tool_call_id)
            if invocation is not None:
                invocation.end = timestamp
                invocation.response_index = index
                invocation.duration = entry.message.duration

    return agents, tools_by_id


def _enclosing_call(parent: AgentInfo, timestamp: datetime) -> ToolInvocation | None:
    for invocation in parent.tool_calls:
        window_end = invocation.end if invocation.end is not None else parent.last
        if invocation.start <= timestamp <= window_end:
            return invocation
    return None


def _link_hierarchy(agents: dict[int, AgentInfo]) -> tuple[list[int], dict[str, list[int]], dict[int, list[int]]]:
    roots: list[int] = []
    call_children: dict[str, list[int]] = {}
    direct_children: dict[int, list[int]] = {}

    for agent in agents.values():
        parent_instance = agent.parent_instance
        if parent_instance is None or parent_instance not in agents:
            roots.append(agent.instance)
            continue
        parent = agents[parent_instance]
        enclosing = _enclosing_call(parent, agent.first)
        if enclosing is not None:
            call_children.setdefault(enclosing.call_id, []).append(agent.instance)
        else:
            direct_children.setdefault(parent_instance, []).append(agent.instance)

    return roots, call_children, direct_children


def _compute_step_durations(agents: dict[int, AgentInfo], entries: list[AgentMessage]) -> dict[int, float]:
    durations: dict[int, float] = {}
    for agent in agents.values():
        previous_timestamp: datetime | None = None
        for index in agent.indices:
            timestamp = _parse_timestamp(entries[index].timestamp)
            if previous_timestamp is not None:
                durations[index] = (timestamp - previous_timestamp).total_seconds()
            previous_timestamp = timestamp
    return durations


def _build_model(entries: list[AgentMessage]) -> LogModel:
    agents, tools_by_id = _build_agents(entries)
    roots, call_children, direct_children = _link_hierarchy(agents)
    step_durations = _compute_step_durations(agents, entries)
    return LogModel(
        entries=entries,
        agents=agents,
        tools_by_id=tools_by_id,
        roots=roots,
        call_children=call_children,
        direct_children=direct_children,
        step_durations=step_durations,
    )


def _max_tool_duration(tools_by_id: dict[str, ToolInvocation]) -> float:
    durations = [tool.duration for tool in tools_by_id.values() if tool.duration is not None]
    return max(durations) if durations else 0.0


def _duration_bar(duration: float | None, max_duration: float) -> str:
    if duration is None:
        return '<span class="dur muted">running…</span>'
    width = 0.0 if max_duration <= 0 else min(100.0, duration / max_duration * 100)
    return (
        f'<span class="dur">{_format_duration(duration)}</span>'
        f'<span class="bar"><span class="bar-fill" style="width:{width:.1f}%"></span></span>'
    )


def _render_tree_call(invocation: ToolInvocation, model: LogModel, max_duration: float) -> str:
    children = model.call_children.get(invocation.call_id, [])
    children_html = "".join(_render_tree_agent(instance, model, max_duration) for instance in children)
    nested = f"<ul>{children_html}</ul>" if children_html else ""
    params = _format_params(invocation.arguments)
    params_html = f'<span class="params">{_escape(params)}</span>' if params else ""
    return (
        f'<li class="node node-call">'
        f'<a class="row" href="#msg-{invocation.request_index}">'
        f'<span class="badge badge-tool">tool</span>'
        f'<span class="node-name">{_escape(invocation.name)}</span>'
        f"{params_html}"
        f"{_duration_bar(invocation.duration, max_duration)}"
        f"</a>{nested}</li>"
    )


def _render_tree_agent(instance: int, model: LogModel, max_duration: float) -> str:
    agent = model.agents[instance]
    call_nodes = "".join(_render_tree_call(call, model, max_duration) for call in agent.tool_calls)
    direct_nodes = "".join(
        _render_tree_agent(child, model, max_duration) for child in model.direct_children.get(instance, [])
    )
    children = call_nodes + direct_nodes
    nested = f"<ul>{children}</ul>" if children else ""
    tokens = _format_tokens(agent.prompt_tokens, agent.completion_tokens)
    tokens_html = f'<span class="tok">{tokens}</span>' if tokens else ""
    return (
        f'<li class="node node-agent" style="--c:{agent.color}">'
        f'<a class="row" href="#agent-{instance}">'
        f'<span class="badge badge-agent">agent</span>'
        f'<span class="node-name">{_escape(agent.name)} <span class="seq">#{agent.seq}</span></span>'
        f'<span class="dur">{_format_duration(agent.duration)}</span>'
        f"{tokens_html}"
        f"</a>{nested}</li>"
    )


def _render_tree(model: LogModel, max_duration: float) -> str:
    roots = "".join(_render_tree_agent(instance, model, max_duration) for instance in model.roots)
    return f'<ul class="tree">{roots}</ul>'


def _render_stats(model: LogModel) -> str:
    timestamps = [_parse_timestamp(entry.timestamp) for entry in model.entries]
    wall_clock = (max(timestamps) - min(timestamps)).total_seconds()
    prompt_tokens = sum(agent.prompt_tokens for agent in model.agents.values())
    completion_tokens = sum(agent.completion_tokens for agent in model.agents.values())
    cells = [
        ("Wall clock", _format_duration(wall_clock)),
        ("Agents", str(len(model.agents))),
        ("Messages", str(len(model.entries))),
        ("Tool calls", str(len(model.tools_by_id))),
        ("Input tokens", f"{prompt_tokens:,}"),
        ("Output tokens", f"{completion_tokens:,}"),
    ]
    cell_html = "".join(
        f'<div class="stat"><span class="stat-value">{value}</span><span class="stat-label">{label}</span></div>'
        for label, value in cells
    )
    return f'<div class="stats">{cell_html}</div>'


def _render_slowest(model: LogModel, max_duration: float) -> str:
    timed = [tool for tool in model.tools_by_id.values() if tool.duration is not None]
    timed.sort(key=lambda tool: tool.duration, reverse=True)
    if not timed:
        return ""
    rows = []
    for tool in timed[:10]:
        agent = model.agents[tool.agent_instance]
        rows.append(
            f'<a class="slow-row" href="#msg-{tool.request_index}">'
            f'<span class="slow-name">{_escape(tool.name)}</span>'
            f'<span class="slow-agent" style="--c:{agent.color}">{_escape(agent.name)} #{agent.seq}</span>'
            f"{_duration_bar(tool.duration, max_duration)}"
            f"</a>"
        )
    return f"<h2>Slowest steps</h2>{''.join(rows)}"


def _slowest_panel(model: LogModel, max_duration: float) -> str:
    body = _render_slowest(model, max_duration)
    return f'<div class="panel slowest">{body}</div>\n' if body else ""


def _render_reasoning(reasoning: str) -> str:
    return f'<details class="reasoning"><summary>Reasoning</summary><pre>{_escape(reasoning)}</pre></details>'


def _render_tool_call_block(tool_call, model: LogModel) -> str:
    invocation = model.tools_by_id.get(tool_call.id)
    links = []
    if invocation is not None and invocation.response_index is not None:
        links.append(f'<a class="xref" href="#msg-{invocation.response_index}">↓ response</a>')
        if invocation.duration is not None:
            links.append(f'<span class="dur">{_format_duration(invocation.duration)}</span>')
    for child in model.call_children.get(tool_call.id, []):
        agent = model.agents[child]
        links.append(f'<a class="xref" href="#agent-{child}">→ {_escape(agent.name)} #{agent.seq}</a>')
    links_html = f'<span class="xrefs">{"".join(links)}</span>' if links else ""
    return (
        f'<div class="tool-call">'
        f'<div class="tool-call-head"><span class="tool-call-name">{_escape(tool_call.function_name)}</span>{links_html}</div>'
        f"<pre>{_escape(_pretty_json(tool_call.arguments))}</pre></div>"
    )


def _render_assistant_body(entry: AgentMessage, model: LogModel) -> str:
    message = entry.message
    parts: list[str] = []
    if isinstance(message, AssistantMessage) and message.reasoning:
        parts.append(_render_reasoning(message.reasoning))
    if isinstance(message, AssistantMessage):
        parts.extend(_render_tool_call_block(tool_call, model) for tool_call in message.tool_calls)
    if message.content:
        parts.append(f'<pre class="content">{_escape(message.content)}</pre>')
    return "".join(parts)


def _render_tool_body(entry: AgentMessage, model: LogModel) -> str:
    invocation = model.tools_by_id.get(entry.message.tool_call_id)
    head = ""
    if invocation is not None:
        head = (
            f'<div class="tool-resp-head">'
            f'<span class="tool-call-name">{_escape(invocation.name)}</span>'
            f'<a class="xref" href="#msg-{invocation.request_index}">↑ call</a>'
            f"</div>"
        )
    return f"{head}<pre>{_escape(entry.message.content)}</pre>"


def _render_body(entry: AgentMessage, model: LogModel) -> str:
    role = entry.message.role
    if role == "assistant":
        return _render_assistant_body(entry, model)
    if role == "tool":
        return _render_tool_body(entry, model)
    return f"<pre>{_escape(entry.message.content or '')}</pre>"


def _render_entry(index: int, model: LogModel, agent: AgentInfo) -> str:
    entry = model.entries[index]
    timestamp = _format_clock(_parse_timestamp(entry.timestamp))
    step = model.step_durations.get(index)
    step_html = f'<span class="step">+{_format_duration(step)}</span>' if step is not None else ""
    tokens = _format_tokens(entry.usage.prompt_tokens, entry.usage.completion_tokens)
    tokens_html = f'<span class="tok">{tokens}</span>' if tokens else ""
    role = entry.message.role
    return (
        f'<div class="entry entry-{role}" id="msg-{index}" style="--c:{agent.color}">'
        f'<div class="entry-meta">'
        f'<span class="role">{role}</span>'
        f'<span class="clock">{timestamp}</span>'
        f"{step_html}{tokens_html}"
        f"</div>"
        f'<div class="entry-body">{_render_body(entry, model)}</div>'
        f"</div>"
    )


def _render_agent_section(agent: AgentInfo, model: LogModel) -> str:
    entries_html = "".join(_render_entry(index, model, agent) for index in agent.indices)
    tokens = _format_tokens(agent.prompt_tokens, agent.completion_tokens)
    tokens_html = f" · {tokens}" if tokens else ""
    parent_html = ""
    if agent.parent_instance is not None and agent.parent_instance in model.agents:
        parent = model.agents[agent.parent_instance]
        parent_html = f' · <a class="xref" href="#agent-{parent.instance}">↑ {_escape(parent.name)} #{parent.seq}</a>'
    return (
        f'<section class="agent-section" id="agent-{agent.instance}" style="--c:{agent.color}">'
        f'<h2 class="agent-head">'
        f'<span class="dot"></span>{_escape(agent.name)} <span class="seq">#{agent.seq}</span>'
        f'<span class="agent-meta">{_format_duration(agent.duration)}{tokens_html}{parent_html}</span>'
        f"</h2>{entries_html}</section>"
    )


def _render_sections(model: LogModel) -> str:
    ordered = sorted(model.agents.values(), key=lambda agent: agent.seq)
    return "".join(_render_agent_section(agent, model) for agent in ordered)


def _generate_css() -> str:
    return """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  margin: 0; background: #0f1419; color: #d7dde5; line-height: 1.5; }
a { color: inherit; text-decoration: none; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 6rem; }
.title { font-size: 1.3rem; font-weight: 600; margin: 0 0 0.25rem; }
.subtitle { color: #7d8a99; font-size: 0.85rem; margin: 0 0 1.5rem; font-family: ui-monospace, monospace; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }
.stat { background: #161c24; border: 1px solid #232c38; border-radius: 10px; padding: 0.85rem 1rem; }
.stat-value { display: block; font-size: 1.25rem; font-weight: 600; }
.stat-label { display: block; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #7d8a99; margin-top: 0.2rem; }
.panel { background: #161c24; border: 1px solid #232c38; border-radius: 12px; padding: 1.1rem 1.3rem; margin-bottom: 1.5rem; }
.panel h2 { margin: 0 0 0.85rem; font-size: 0.95rem; color: #9fb0c3; text-transform: uppercase; letter-spacing: 0.05em; }
.tree, .tree ul { list-style: none; margin: 0; padding: 0; }
.tree ul { margin-left: 1.1rem; border-left: 1px solid #2a3543; padding-left: 0.6rem; }
.node { margin: 0.15rem 0; }
.row { display: flex; align-items: center; gap: 0.55rem; padding: 0.3rem 0.5rem; border-radius: 7px; }
.row:hover { background: #1d2530; }
.badge { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.1rem 0.4rem; border-radius: 5px; font-weight: 700; }
.badge-agent { background: var(--c, #4f8cff); color: #0f1419; }
.badge-tool { background: #2a3543; color: #9fb0c3; }
.node-name { font-weight: 500; }
.node-agent > .row .node-name { color: var(--c, #d7dde5); }
.seq { color: #6b7888; font-weight: 400; font-size: 0.85em; }
.params { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: #8b97a6; font-family: ui-monospace, monospace; font-size: 0.78rem; }
.dur { font-variant-numeric: tabular-nums; font-size: 0.8rem; color: #c7d0db; font-family: ui-monospace, monospace; white-space: nowrap; }
.dur.muted { color: #6b7888; }
.tok { font-size: 0.75rem; color: #6b7888; font-family: ui-monospace, monospace; }
.bar { flex: 0 0 120px; height: 6px; background: #232c38; border-radius: 3px; overflow: hidden; }
.bar-fill { display: block; height: 100%; background: linear-gradient(90deg, #4f8cff, #ff7f4e); }
.slowest h2 { margin: 0 0 0.75rem; font-size: 0.95rem; color: #9fb0c3; text-transform: uppercase; letter-spacing: 0.05em; }
.slow-row { display: flex; align-items: center; gap: 0.7rem; padding: 0.35rem 0.5rem; border-radius: 7px; }
.slow-row:hover { background: #1d2530; }
.slow-name { font-weight: 500; min-width: 120px; }
.slow-agent { font-size: 0.75rem; color: var(--c, #7d8a99); min-width: 150px; }
.agent-section { background: #161c24; border: 1px solid #232c38; border-left: 4px solid var(--c, #4f8cff);
  border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 1.2rem; scroll-margin-top: 1rem; }
.agent-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin: 0 0 0.85rem; font-size: 1.05rem; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--c, #4f8cff); }
.agent-meta { font-size: 0.78rem; color: #7d8a99; font-weight: 400; font-family: ui-monospace, monospace; }
.entry { border-top: 1px solid #232c38; padding: 0.7rem 0; scroll-margin-top: 1rem; }
.entry-meta { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem; }
.role { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;
  padding: 0.1rem 0.45rem; border-radius: 5px; background: #2a3543; color: #9fb0c3; }
.entry-assistant .role { background: #1f3a5f; color: #8fc0ff; }
.entry-user .role { background: #1f4a32; color: #8fe0ab; }
.entry-tool .role { background: #4a3a1f; color: #e0c08f; }
.entry-system .role { background: #3a2f4a; color: #c8a8e8; }
.clock { font-size: 0.75rem; color: #6b7888; font-family: ui-monospace, monospace; }
.step { font-size: 0.75rem; color: #d8a05f; font-family: ui-monospace, monospace; }
pre { background: #0f1419; border: 1px solid #232c38; border-radius: 7px; padding: 0.7rem 0.85rem; margin: 0.4rem 0 0;
  overflow-x: auto; font-size: 0.82rem; white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, monospace; }
.reasoning summary { cursor: pointer; color: #7d8a99; font-size: 0.8rem; font-style: italic; padding: 0.2rem 0; }
.tool-call { margin: 0.4rem 0; }
.tool-call-head, .tool-resp-head { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.tool-call-name { color: #8fc0ff; font-weight: 600; font-size: 0.85rem; font-family: ui-monospace, monospace; }
.xrefs { display: flex; gap: 0.6rem; align-items: center; }
.xref { font-size: 0.75rem; color: #6b9fff; }
.xref:hover { text-decoration: underline; }
.content { background: #12181f; }
"""


def _build_document(model: LogModel, filename: str) -> str:
    max_duration = _max_tool_duration(model.tools_by_id)
    root_names = ", ".join(_escape(model.agents[instance].name) for instance in model.roots)
    timestamps = [_parse_timestamp(entry.timestamp) for entry in model.entries]
    time_range = f"{_format_clock(min(timestamps))} – {_format_clock(max(timestamps))}"
    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>Agent Log – {root_names}</title>\n"
        f"<style>{_generate_css()}</style>\n"
        "</head>\n<body>\n<div class='wrap'>\n"
        f'<h1 class="title">{root_names}</h1>\n'
        f'<p class="subtitle">{_escape(filename)} · {time_range}</p>\n'
        f"{_render_stats(model)}\n"
        f'<div class="panel"><h2>Agent &amp; tool tree</h2>{_render_tree(model, max_duration)}</div>\n'
        f"{_slowest_panel(model, max_duration)}"
        f"{_render_sections(model)}\n"
        "</div>\n</body>\n</html>\n"
    )


def _read_log_file(log_path: Path) -> list[AgentMessage]:
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    return [AgentMessage.from_dict(json.loads(line)) for line in lines if line.strip()]


def html_from_log(log_path: str) -> str:
    path = Path(log_path)
    entries = _read_log_file(path)
    model = _build_model(entries)
    return _build_document(model, path.name)
