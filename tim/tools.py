import logging
from typing import Annotated
from tim import Project


logger = logging.getLogger(__name__)


def _numbered(lines: list[str], offset: int = 1) -> str:
    return "".join(f"{offset + i}\t{line}" for i, line in enumerate(lines))


def view_file(
    project: Project,
    path: Annotated[str, "Path to the file to view"],
    start_line: Annotated[int | None, "First line to show (1-indexed, inclusive)"] = None,
    end_line: Annotated[int | None, "Last line to show (1-indexed, inclusive)"] = None,
) -> str:
    """Show file contents with line numbers. Optionally restrict to a line range."""
    logger.debug(f"view_file {path} lines={start_line}-{end_line}")
    try:
        lines = project.path(path).read_text().splitlines(keepends=True)
    except IsADirectoryError:
        return f"Tool Error: {path} is a directory"
    except FileNotFoundError:
        return f"Tool Error: {path} not found"
    start_index = (start_line or 1) - 1
    end_index = end_line if end_line is not None else len(lines)
    return _numbered(lines[start_index:end_index], offset=start_index + 1)


def create_file(
    project: Project,
    path: Annotated[str, "Path to the new file"],
    content: Annotated[str, "File content"],
) -> str:
    """Create a new file with the given content, creating dirs if required. Overwrites file if already exists."""
    logger.debug(f"create_file {path}")
    path = project.path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content)
    lines = content.splitlines(keepends=True)
    return f"Wrote {len(lines)} lines"


def edit_file(
    project: Project,
    path: Annotated[str, "Path to the file to edit"],
    start_line: Annotated[int, "First line of the range to replace (1-indexed, inclusive)"],
    end_line: Annotated[
        int,
        "Last line of the range to replace (1-indexed, inclusive). Set to start_line - 1 to insert without replacing.",
    ],
    new_content: Annotated[str, "Replacement text. Empty string to delete the range."],
) -> str:
    """Replace, insert, or delete lines in a file. Returns the updated file with line numbers."""
    logger.debug(f"edit_file {path} lines={start_line}-{end_line}")
    path = project.path(path)
    lines = path.read_text().splitlines(keepends=True)
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    replacement = new_content.splitlines(keepends=True) if new_content else []
    lines[start_line - 1 : end_line] = replacement
    result = "".join(lines)
    path.write_text(result)
    return _numbered(lines)


def run(
    project: Project,
    command: Annotated[str, "Shell command to run in the project root"],
    timeout: Annotated[int, "Timeout in seconds"] = 120,
) -> str:
    """Run a shell command in the project root and return its output"""
    return project.run(command=command, timeout=timeout).formatted()


def ls(project: Project, path: Annotated[str, "Filesystem path to list"]) -> str:
    """List the contents of a directory"""
    path = project.path(path)
    logger.debug(f"ls {path}")
    result = project.run(f"ls -la {path}")
    logger.debug(f"ls {path} -> {result!r}")
    return result.formatted()


all_tools = (  # type: ignore[assignment]
    view_file,
    edit_file,
    create_file,
    run,
    ls,
)
