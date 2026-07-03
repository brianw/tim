import pytest
from dataclasses import FrozenInstanceError
from tim.change import Change


class TestChangeDataclass:
    def test_change_is_frozen(self):
        change = Change(
            title="Test Title",
            desc="Test description",
            shoulds=["should1"],
            musts=["must1"],
            approvals=["approver1"],
        )

        with pytest.raises(FrozenInstanceError):
            change.title = "Modified Title"

        with pytest.raises(FrozenInstanceError):
            change.desc = "Modified description"

        with pytest.raises(FrozenInstanceError):
            change.shoulds = ["modified"]

        with pytest.raises(FrozenInstanceError):
            change.musts = ["modified"]

        with pytest.raises(FrozenInstanceError):
            change.approvals = ["modified"]

    def test_change_field_access(self):
        change = Change(
            title="My Change",
            desc="A description",
            shoulds=["should do this"],
            musts=["must do that"],
            approvals=["alice", "bob"],
        )

        assert change.title == "My Change"
        assert change.desc == "A description"
        assert change.shoulds == ["should do this"]
        assert change.musts == ["must do that"]
        assert change.approvals == ["alice", "bob"]

    def test_change_with_none_desc(self):
        change = Change(
            title="No Description",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
        )

        assert change.title == "No Description"
        assert change.desc is None

    def test_change_with_all_empty_lists(self):
        change = Change(
            title="Empty Lists",
            desc="Some description",
            shoulds=[],
            musts=[],
            approvals=[],
        )

        assert change.shoulds == []
        assert change.musts == []
        assert change.approvals == []

    def test_change_equality(self):
        change1 = Change(
            title="Same Title",
            desc="Same desc",
            shoulds=["s1"],
            musts=["m1"],
            approvals=[],
        )
        change2 = Change(
            title="Same Title",
            desc="Same desc",
            shoulds=["s1"],
            musts=["m1"],
            approvals=[],
        )

        assert change1 == change2

    def test_change_inequality(self):
        change1 = Change(
            title="Title1",
            desc="Desc1",
            shoulds=[],
            musts=[],
            approvals=[],
        )
        change2 = Change(
            title="Title2",
            desc="Desc1",
            shoulds=[],
            musts=[],
            approvals=[],
        )

        assert change1 != change2


class TestChangeYaml:
    def test_round_trip(self):
        change = Change(
            title="Add YAML support",
            desc="Serialize a change",
            shoulds=["Be readable"],
            musts=["Round trip"],
            approvals=["brian"],
        )

        assert Change.from_yaml(change.to_yaml()) == change

    def test_round_trip_with_optional_values(self):
        change = Change(
            title="Minimal change",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
        )

        assert Change.from_yaml(change.to_yaml()) == change
