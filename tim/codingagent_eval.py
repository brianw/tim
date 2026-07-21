from tim.codingagent import CodingAgent
from tim.change import Change


def test_creates_file_using_tools(project_jsonprinter):
    change = Change(
        title="Add INSTALL.md documentation",
        desc="Create an INSTALL.md with instructions on how to install and setup this project on a local machine.",
        shoulds=[],
        musts=[
            "Create INSTALL.md in the project root.",
            "Use the native package manager for this project.",
            "Do NOT provide instructions for alternate package managers",
        ],
        approvals=["INSTALL.md exists"],
    )
    target_file = project_jsonprinter.root / "INSTALL.md"
    assert not target_file.exists(), "INSTALL.md already present before agent start"

    agent = CodingAgent(project_jsonprinter, change)
    agent.start()
    assert target_file.exists(), "INSTALL.md not present after agent completed"

    instructions = target_file.read_text()
    assert "uv sync" in instructions, "`uv sync` missing from instructions"

    assert any(tool.function_name == "create_file" for tool in agent.tool_calls), "create_file not used"
    assert not any([tool.function_name == "run" and ">" in tool.arguments for tool in agent.tool_calls]), (
        "run() called with redirection"
    )
