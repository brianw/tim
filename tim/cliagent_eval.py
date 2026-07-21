from tim.cliagent import CliAgent


def test_checks_project_state_before_advice(project_jsonprinter):
    code_before = project_jsonprinter.path("cli.py").read_text()
    agent = CliAgent(project_jsonprinter)
    agent.add_user_message(
        "The -v option in the cli has to come before the subcommand. What are my options (don't write any code yet) for allowing that to appear anywhere in the argument list?"
    )
    response = agent.start()
    assert "click" in response, "Agent didn't answer relating to the click library"
    assert len(agent.tool_calls) > 0, "No tool calls used, agent answered without checking current project state"

    code_after = project_jsonprinter.path("cli.py").read_text()
    assert code_before == code_after, "Agent modified code, despite being instructed not to"


def test_skips_project_state_for_general_advice(project_empty):
    agent = CliAgent(project_empty)
    agent.add_user_message("Explain this Python syntax: `items[:] = [item for item in items if <some condition>]`")
    response = agent.start()
    assert len(response) > 128, "Unexpectedly short response"
    assert len(agent.tool_calls) == 0, "Performed tool calls for question unrelated to project state"
