from tim.change import Change
from tim.codingagent import format_change


def make_change(**values) -> Change:
    return Change(
        title=values.get("title", "Test"),
        desc=values.get("desc"),
        shoulds=values.get("shoulds", []),
        musts=values.get("musts", []),
        approvals=[],
    )


def test_format_change_description():
    result = format_change(make_change(title="Add Feature", desc="This adds a feature"))

    assert "--- Add Feature ---" in result
    assert "This adds a feature" in result


def test_format_change_shoulds():
    result = format_change(make_change(shoulds=["Handle invalid credentials", "Show an error"]))

    assert "You SHOULD:\n- Handle invalid credentials\n- Show an error" in result


def test_format_change_musts():
    result = format_change(make_change(musts=["Use parameterized queries", "Validate inputs"]))

    assert "You MUST:\n- Use parameterized queries\n- Validate inputs" in result


def test_format_change_omits_empty_sections():
    result = format_change(make_change(desc="A simple task"))

    assert "You SHOULD:" not in result
    assert "You MUST:" not in result
