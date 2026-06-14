import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_AGENT_COLORS: list[str] = [
    "#E41A1C",
    "#FF7F4E",
    "#FFB347",
    "#FFCC66",
    "#FFFF66",
    "#CCFF66",
    "#99D94C",
    "#66CC44",
    "#4DBB72",
    "#33CC99",
    "#33B5E5",
    "#4B4ABF",
    "#8E44AD",
    "#B94498",
    "#E91E8C",
    "#FF5C8A",
    "#FF9999",
    "#CC99FF",
    "#99CCFF",
    "#99FFCC",
    "#FF9966",
    "#6699CC",
    "#996633",
    "#336699",
    "#993366",
    "#CC6699",
    "#996666",
    "#669966",
    "#666699",
    "#999966",
    "#669999",
    "#996699",
    "#663366",
    "#336633",
    "#336666",
    "#993399",
]


@dataclass
class LogEntry:
    agent: str
    agent_instance: int
    timestamp: datetime
    message_role: str
    message_content: str | None
    reasoning: str | None
    tool_calls: list[dict]
    tool_id: str | None
    usage_prompt_tokens: int | None
    usage_completion_tokens: int | None


@dataclass
class LogMetadata:
    filename: str
    agent: str
    entry_count: int
    start_time: str
    end_time: str


def _parse_timestamp(timestamp_string: str) -> datetime:
    return datetime.fromisoformat(timestamp_string)


def _format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second" if seconds == 1 else f"{seconds} seconds"

    total_minutes = seconds // 60
    remaining_seconds = seconds % 60
    if total_minutes < 60:
        minutes_label = "minute" if total_minutes == 1 else "minutes"
        if remaining_seconds:
            return f"{total_minutes} {minutes_label} {remaining_seconds:02d} seconds"
        return f"{total_minutes} {minutes_label}"

    total_hours = total_minutes // 60
    remaining_minutes = total_minutes % 60
    hours_label = "hour" if total_hours == 1 else "hours"
    if remaining_minutes:
        return f"{total_hours} {hours_label} {remaining_minutes:02d} minutes"
    return f"{total_hours} {hours_label}"


def _format_usage(prompt_tokens: int | None, completion_tokens: int | None) -> str | None:
    tokens: list[str] = []
    if prompt_tokens is not None:
        tokens.append(f"{prompt_tokens} input")
    if completion_tokens is not None:
        tokens.append(f"{completion_tokens} output")
    return " | ".join(tokens) if tokens else None


def _parse_log_entry(raw: dict) -> LogEntry:
    source = raw["source"]
    message = raw["message"]
    timestamp = _parse_timestamp(raw["at"])

    return LogEntry(
        agent=source["agent"],
        agent_instance=source["agent_instance"],
        timestamp=timestamp,
        message_role=message["role"],
        message_content=message.get("content"),
        reasoning=message.get("reasoning"),
        tool_calls=message.get("tool_calls", []),
        tool_id=message.get("id"),
        usage_prompt_tokens=raw.get("usage", {}).get("prompt_tokens"),
        usage_completion_tokens=raw.get("usage", {}).get("completion_tokens"),
    )


def _build_header(metadata: LogMetadata) -> str:
    time_range = f"{metadata.start_time} - {metadata.end_time}"
    header_content = f"{metadata.filename} | {metadata.entry_count} entries | {time_range}"
    return header_content


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _render_system_message(entry: LogEntry) -> str:
    escaped_content = _escape(entry.message_content or "")
    return (
        f'<div class="message message-system"><div class="message-role">System</div><pre>{escaped_content}</pre></div>'
    )


def _render_user_message(entry: LogEntry) -> str:
    escaped_content = _escape(entry.message_content or "")
    return f'<div class="message message-user"><div class="message-role">User</div><pre>{escaped_content}</pre></div>'


def _render_assistant_message(entry: LogEntry) -> str:
    parts: list[str] = []

    if entry.reasoning:
        escaped_reasoning = _escape(entry.reasoning)
        parts.append(
            f'<div class="reasoning-section">'
            f'<div class="reasoning-label">Reasoning</div>'
            f"<pre>{escaped_reasoning}</pre>"
            f"</div>"
        )

    for tool_call in entry.tool_calls:
        tool_name = tool_call.get("name", "unknown")
        tool_id = tool_call.get("id", "unknown")
        tool_arguments = tool_call.get("arguments", "{}")
        escaped_arguments = _escape(tool_arguments)
        parts.append(
            f'<div class="tool-call-section">'
            f'<div class="tool-call-label">Tool Call: {tool_name} ({tool_id})</div>'
            f"<pre>{escaped_arguments}</pre>"
            f"</div>"
        )

    if entry.message_content:
        escaped_content = _escape(entry.message_content)
        parts.append(f'<div class="message-content"><pre>{escaped_content}</pre></div>')

    if entry.usage_prompt_tokens is not None or entry.usage_completion_tokens is not None:
        usage = _format_usage(entry.usage_prompt_tokens, entry.usage_completion_tokens)
        if usage:
            parts.append(
                f'<div class="usage-section"><div class="usage-label">Token Usage</div><span>{usage}</span></div>'
            )

    return f'<div class="message message-assistant"><div class="message-role">Assistant</div>{"".join(parts)}</div>'


def _render_tool_message(entry: LogEntry) -> str:
    content = entry.message_content if entry.message_content is not None else ""
    escaped_content = _escape(content)
    return (
        f'<div class="message message-tool">'
        f'<div class="message-role">Tool Response</div>'
        f"<pre>{escaped_content}</pre></div>"
    )


def _collect_agents(entries: list[LogEntry]) -> dict[tuple[str, int], int]:
    agent_color_index: dict[tuple[str, int], int] = {}
    color_index = 0
    for entry in entries:
        agent_key = (entry.agent, entry.agent_instance)
        if agent_key not in agent_color_index:
            agent_color_index[agent_key] = color_index
            color_index += 1
    return agent_color_index


def _agent_color(index: int) -> str:
    return _AGENT_COLORS[index % len(_AGENT_COLORS)]


def _entry_border_style(entry: LogEntry, agent_colors: dict[tuple[str, int], int]) -> str:
    agent_key = (entry.agent, entry.agent_instance)
    if agent_key not in agent_colors:
        return ""
    color = _agent_color(agent_colors[agent_key])
    return f'style="border-left: 5px solid {color};"'


def _render_entry(
    entry: LogEntry, agent_colors: dict[tuple[str, int], int], duration_seconds: int | None = None
) -> str:
    role = entry.message_role
    if role == "system":
        message_html = _render_system_message(entry)
    elif role == "user":
        message_html = _render_user_message(entry)
    elif role == "assistant":
        message_html = _render_assistant_message(entry)
    elif role == "tool":
        message_html = _render_tool_message(entry)
    else:
        message_html = _render_user_message(entry)

    timestamp_str = _format_timestamp(entry.timestamp)
    agent_label = f"{entry.agent} ({entry.agent_instance})"
    usage_str = _format_usage(entry.usage_prompt_tokens, entry.usage_completion_tokens)
    usage_html = f'<span class="usage">{usage_str}</span>' if usage_str else ""
    duration_html = (
        f'<span class="duration">({_format_duration(duration_seconds)})</span>' if duration_seconds is not None else ""
    )
    border_style = _entry_border_style(entry, agent_colors)

    return (
        f'<div class="log-entry" {border_style}>'
        f'<div class="log-meta">'
        f'<span class="timestamp">{timestamp_str}</span>'
        f"{duration_html}"
        f'<span class="agent-label">{agent_label}</span>'
        f"{usage_html}"
        f"</div>"
        f'<div class="log-body">{message_html}</div>'
        f"</div>"
    )


def _generate_css() -> str:
    return (
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
        "max-width: 960px; margin: 0 auto; padding: 2rem; background: #f5f5f5; color: #333; } "
        ".header { background: #2c3e50; color: white; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; } "
        ".header h1 { margin: 0 0 0.5rem 0; font-size: 1.5rem; } "
        ".header p { margin: 0; opacity: 0.8; font-size: 0.9rem; } "
        ".log-meta { background: #f8f9fa; padding: 0.5rem 1rem; border-bottom: 1px solid #eee; display: flex; gap: 1rem; font-size: 0.85rem; } "
        ".timestamp { color: #666; } "
        ".duration { color: #888; font-size: 0.8rem; } "
        ".agent-label { color: #2c3e50; font-weight: 500; } "
        ".usage { color: #999; } "
        ".log-body { padding: 1rem; } "
        ".message { margin-bottom: 1rem; } "
        ".message:last-child { margin-bottom: 0; } "
        ".message-role { font-weight: 600; font-size: 0.85rem; text-transform: uppercase; color: #666; margin-bottom: 0.25rem; } "
        ".reasoning-section { margin-bottom: 0.75rem; } "
        ".reasoning-label { font-size: 0.8rem; color: #888; font-style: italic; margin-bottom: 0.25rem; } "
        ".tool-call-section { margin-bottom: 0.75rem; } "
        ".tool-call-label { font-size: 0.85rem; color: #1976d2; font-weight: 500; margin-bottom: 0.25rem; } "
        ".usage-section { font-size: 0.8rem; color: #666; margin-top: 0.5rem; } "
        ".usage-label { font-weight: 500; margin-right: 0.25rem; } "
        "pre { background: #f8f9fa; padding: 0.75rem; border-radius: 4px; overflow-x: auto; font-size: 0.9rem; "
        "white-space: pre-wrap; word-wrap: break-word; margin: 0; } "
        "code { background: #e9ecef; padding: 0.15rem 0.35rem; border-radius: 3px; font-size: 0.85em; }"
    )


def _build_html_header(metadata: LogMetadata, css: str) -> str:
    header_content = _build_header(metadata)
    return (
        f"<!DOCTYPE html>\n"
        f"<html lang='en'>\n"
        f"<head>\n"
        f"<meta charset='utf-8'>\n"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>Agent Log - {html.escape(metadata.agent)}</title>\n"
        f"<style>{css}</style>\n"
        f"</head><body>\n"
        f'<div class="header"><h1>Agent Log - {html.escape(metadata.agent)}</h1>'
        f"<p>{header_content}</p></div>\n"
    )


def _build_html_footer() -> str:
    return "</body></html>\n"


def _read_log_file(log_path: Path) -> list[dict]:
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def _extract_metadata(entries: list[dict], log_path: Path) -> LogMetadata:
    timestamps = [_parse_timestamp(entry["at"]) for entry in entries]
    agent = entries[0]["source"]["agent"]
    start_time = _format_timestamp(min(timestamps))
    end_time = _format_timestamp(max(timestamps))
    filename = log_path.name

    return LogMetadata(
        filename=filename,
        agent=agent,
        entry_count=len(entries),
        start_time=start_time,
        end_time=end_time,
    )


def _parse_log_entries(raw_entries: list[dict]) -> list[LogEntry]:
    return [_parse_log_entry(raw) for raw in raw_entries]


def html_from_log(log_path: str) -> str:
    log_file_path = Path(log_path)
    raw_entries = _read_log_file(log_file_path)
    metadata = _extract_metadata(raw_entries, log_file_path)
    entries = _parse_log_entries(raw_entries)
    agent_colors = _collect_agents(entries)

    css = _generate_css()
    html_parts = [_build_html_header(metadata, css)]

    previous_entry: LogEntry | None = None
    for entry in entries:
        duration_seconds: int | None = None
        if previous_entry is not None:
            duration_seconds = int((entry.timestamp - previous_entry.timestamp).total_seconds())
        entry_html = _render_entry(entry, agent_colors, duration_seconds)
        html_parts.append(entry_html)
        previous_entry = entry

    html_parts.append(_build_html_footer())

    return "\n".join(html_parts)
