import pytest

from tim.change import Change
from tim.cliagent import ExtractChangeAgent


@pytest.fixture
def agent():
    return object.__new__(ExtractChangeAgent)


@pytest.fixture
def answer():
    return {
        "title": "Add YAML changes",
        "desc": "Serialize changes to YAML",
        "shoulds": ["Keep the format readable"],
        "musts": ["Round trip without data loss"],
        "approvals": ["pytest tim/change_test.py"],
    }


def test_validate_answer(agent, answer):
    assert agent.validate_answer(answer)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", None),
        ("desc", []),
        ("shoulds", "readable"),
        ("musts", [1]),
        ("approvals", None),
    ],
)
def test_validate_answer_rejects_invalid_fields(agent, answer, field, value):
    answer[field] = value

    assert not agent.validate_answer(answer)


def test_validate_answer_rejects_missing_field(agent, answer):
    del answer["approvals"]

    assert not agent.validate_answer(answer)


def test_format_answer(agent, answer):
    assert agent.format_answer(answer) == Change(**answer)
