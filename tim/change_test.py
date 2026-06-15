import pytest
from pathlib import Path
from dataclasses import FrozenInstanceError
from tim.change import Change, ChangeBuilder


class TestChangeDataclass:
    def test_change_is_frozen(self):
        change = Change(
            title="Test Title",
            desc="Test description",
            shoulds=["should1"],
            musts=["must1"],
            approvals=["approver1"],
            branch="feature/test",
            log_path=Path("/tmp/log.txt"),
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

        with pytest.raises(FrozenInstanceError):
            change.branch = "modified"

        with pytest.raises(FrozenInstanceError):
            change.log_path = Path("/modified/path")

    def test_change_field_access(self):
        change = Change(
            title="My Change",
            desc="A description",
            shoulds=["should do this"],
            musts=["must do that"],
            approvals=["alice", "bob"],
            branch="feature/my-feature",
            log_path=Path("/var/log/change.log"),
        )

        assert change.title == "My Change"
        assert change.desc == "A description"
        assert change.shoulds == ["should do this"]
        assert change.musts == ["must do that"]
        assert change.approvals == ["alice", "bob"]
        assert change.branch == "feature/my-feature"
        assert change.log_path == Path("/var/log/change.log")

    def test_change_with_none_desc(self):
        change = Change(
            title="No Description",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
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
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        assert change.shoulds == []
        assert change.musts == []
        assert change.approvals == []

    def test_change_with_none_branch(self):
        change = Change(
            title="No Branch",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        assert change.branch is None

    def test_change_equality(self):
        change1 = Change(
            title="Same Title",
            desc="Same desc",
            shoulds=["s1"],
            musts=["m1"],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )
        change2 = Change(
            title="Same Title",
            desc="Same desc",
            shoulds=["s1"],
            musts=["m1"],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        assert change1 == change2

    def test_change_inequality(self):
        change1 = Change(
            title="Title1",
            desc="Desc1",
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )
        change2 = Change(
            title="Title2",
            desc="Desc1",
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        assert change1 != change2


class TestChangeFormat:
    def _make_change(self, **kwargs):
        return Change(
            title="Test",
            desc=None,
            shoulds=kwargs.get("shoulds", []),
            musts=kwargs.get("musts", []),
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

    def test_format_empty_steps(self):
        change = self._make_change()
        assert change._format("Test Title", []) == ""

    def test_format_single_step(self):
        change = self._make_change()
        result = change._format("Steps:", ["first step"])
        assert result == "Steps:\n- first step"

    def test_format_multiple_steps(self):
        change = self._make_change()
        result = change._format("Steps:", ["step 1", "step 2", "step 3"])
        assert result == "Steps:\n- step 1\n- step 2\n- step 3"

    def test_format_step_with_special_chars(self):
        change = self._make_change()
        result = change._format("Notes:", ["do 'this'", 'do "that"', "do & stuff"])
        assert result == "Notes:\n- do 'this'\n- do \"that\"\n- do & stuff"

    def test_format_step_with_newline_in_step(self):
        change = self._make_change()
        result = change._format("Steps:", ["step with\nembedded newline"])
        assert result == "Steps:\n- step with\nembedded newline"


class TestChangeFullDescription:
    def test_basic_title_only(self):
        change = Change(
            title="My Change",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "--- My Change ---" in result
        assert "None" in result

    def test_with_description(self):
        change = Change(
            title="Add Feature",
            desc="This adds a new feature",
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "--- Add Feature ---" in result
        assert "This adds a new feature" in result
        assert "None" not in result

    def test_with_shoulds(self):
        change = Change(
            title="Implement Login",
            desc="Add user authentication",
            shoulds=["Handle invalid credentials", "Show error message"],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "You SHOULD:" in result
        assert "- Handle invalid credentials" in result
        assert "- Show error message" in result

    def test_with_musts(self):
        change = Change(
            title="Fix Security Bug",
            desc="Patch SQL injection vulnerability",
            shoulds=[],
            musts=["Use parameterized queries", "Validate all inputs"],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "You MUST:" in result
        assert "- Use parameterized queries" in result
        assert "- Validate all inputs" in result

    def test_with_both_shoulds_and_musts(self):
        change = Change(
            title="Refactor Module",
            desc="Improve code structure",
            shoulds=["Add logging", "Update docstrings"],
            musts=["Pass all existing tests", "Maintain API compatibility"],
            approvals=["senior-dev"],
            branch="refactor/module",
            log_path=Path("/var/log/refactor.log"),
        )

        result = change.full_description()
        assert "--- Refactor Module ---" in result
        assert "Improve code structure" in result
        assert "You SHOULD:" in result
        assert "Add logging" in result
        assert "Update docstrings" in result
        assert "You MUST:" in result
        assert "Pass all existing tests" in result
        assert "Maintain API compatibility" in result

    def test_with_none_description(self):
        change = Change(
            title="Quick Fix",
            desc=None,
            shoulds=["Check edge cases"],
            musts=["Fix the bug"],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "--- Quick Fix ---" in result
        assert "You SHOULD:" in result
        assert "Check edge cases" in result
        assert "You MUST:" in result
        assert "Fix the bug" in result
        assert "None" in result

    def test_with_empty_lists(self):
        change = Change(
            title="Simple Task",
            desc="A simple task with no requirements",
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "--- Simple Task ---" in result
        assert "A simple task with no requirements" in result
        assert "You SHOULD:" not in result
        assert "You MUST:" not in result

    def test_output_is_stripped(self):
        change = Change(
            title="Test",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert result == result.strip()

    def test_full_description_contains_title_separator(self):
        change = Change(
            title="Important Change",
            desc=None,
            shoulds=[],
            musts=[],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "--- Important Change ---" in result

    def test_full_description_multiline_description(self):
        change = Change(
            title="Complex Change",
            desc="Line 1\nLine 2\nLine 3",
            shoulds=["step 1"],
            musts=["step 2"],
            approvals=[],
            branch=None,
            log_path=Path("/tmp/log.txt"),
        )

        result = change.full_description()
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert "step 1" in result
        assert "step 2" in result


class TestChangeBuilder:
    def test_basic_build_with_just_title(self):
        change = ChangeBuilder("My Change").build()

        assert change.title == "My Change"
        assert change.desc is None
        assert change.shoulds == []
        assert change.musts == []
        assert change.approvals == []
        assert change.branch is None
        assert change.log_path is None

    def test_building_with_all_fields(self):
        change = (
            ChangeBuilder("Complete Change")
            .desc("This is a complete change description")
            .shoulds(["should1", "should2"])
            .musts(["must1", "must2"])
            .approvals(["alice", "bob"])
            .branch("feature/complete")
            .log_path(Path("/var/log/complete.log"))
            .build()
        )

        assert change.title == "Complete Change"
        assert change.desc == "This is a complete change description"
        assert change.shoulds == ["should1", "should2"]
        assert change.musts == ["must1", "must2"]
        assert change.approvals == ["alice", "bob"]
        assert change.branch == "feature/complete"
        assert change.log_path == Path("/var/log/complete.log")

    def test_chaining_methods(self):
        builder = ChangeBuilder("Chained")
        assert builder.desc("desc").shoulds(["s1"]) is not None
        assert builder.musts(["m1"]).approvals(["a1"]) is not None
        assert builder.branch("main").log_path(Path("/tmp")) is not None

        change = builder.build()
        assert change.title == "Chained"
        assert change.desc == "desc"
        assert change.shoulds == ["s1"]
        assert change.musts == ["m1"]
        assert change.approvals == ["a1"]
        assert change.branch == "main"
        assert change.log_path == Path("/tmp")

    def test_default_values_for_optional_fields(self):
        change = ChangeBuilder("Test").build()

        assert change.desc is None
        assert change.shoulds == []
        assert change.musts == []
        assert change.approvals == []
        assert change.branch is None
        assert change.log_path is None

    def test_desc_method_with_dedent(self):
        change = (
            ChangeBuilder("Test")
            .desc(
                """
                This is a multi-line description.
                It has leading indentation.
                """
            )
            .build()
        )

        assert change.desc == "This is a multi-line description.\nIt has leading indentation."

    def test_desc_method_strips_whitespace(self):
        change = ChangeBuilder("Test").desc("   \n  leading and trailing spaces  \n  ").build()

        assert change.desc == "leading and trailing spaces"

    def test_shoulds_with_empty_list(self):
        change = ChangeBuilder("Test").shoulds([]).build()
        assert change.shoulds == []

    def test_shoulds_with_items(self):
        change = ChangeBuilder("Test").shoulds(["item1", "item2"]).build()
        assert change.shoulds == ["item1", "item2"]

    def test_shoulds_copies_list(self):
        items = ["item1"]
        change = ChangeBuilder("Test").shoulds(items).build()

        items.append("item2")
        assert change.shoulds == ["item1"]

    def test_musts_with_empty_list(self):
        change = ChangeBuilder("Test").musts([]).build()
        assert change.musts == []

    def test_musts_with_items(self):
        change = ChangeBuilder("Test").musts(["item1", "item2"]).build()
        assert change.musts == ["item1", "item2"]

    def test_musts_copies_list(self):
        items = ["item1"]
        change = ChangeBuilder("Test").musts(items).build()

        items.append("item2")
        assert change.musts == ["item1"]

    def test_approvals_with_empty_list(self):
        change = ChangeBuilder("Test").approvals([]).build()
        assert change.approvals == []

    def test_approvals_with_items(self):
        change = ChangeBuilder("Test").approvals(["alice", "bob"]).build()
        assert change.approvals == ["alice", "bob"]

    def test_approvals_copies_list(self):
        items = ["alice"]
        change = ChangeBuilder("Test").approvals(items).build()

        items.append("bob")
        assert change.approvals == ["alice"]

    def test_branch_setting_branch_name(self):
        change = ChangeBuilder("Test").branch("feature/test-branch").build()
        assert change.branch == "feature/test-branch"

    def test_branch_default_is_none(self):
        change = ChangeBuilder("Test").build()
        assert change.branch is None

    def test_log_path_setting_log_path(self):
        path = Path("/var/log/my-change.log")
        change = ChangeBuilder("Test").log_path(path).build()
        assert change.log_path == path

    def test_log_path_default_is_none(self):
        change = ChangeBuilder("Test").build()
        assert change.log_path is None

    def test_builder_returns_change_instance(self):
        change = ChangeBuilder("Test").build()
        assert isinstance(change, Change)

    def test_multiple_builds_independent(self):
        change1 = ChangeBuilder("First").desc("First desc").build()
        change2 = ChangeBuilder("Second").desc("Second desc").build()

        assert change1.title == "First"
        assert change2.title == "Second"
        assert change1.desc == "First desc"
        assert change2.desc == "Second desc"

    def test_desc_with_complex_indentation(self):
        change = (
            ChangeBuilder("Test")
            .desc(
                """
                    This has 4 spaces of indentation.
                        And this has 8 spaces of indentation.
                    Back to 4 spaces.
                """
            )
            .build()
        )

        assert "This has 4 spaces of indentation." in change.desc
        assert "And this has 8 spaces of indentation." in change.desc
        assert "Back to 4 spaces." in change.desc

    def test_full_builder_workflow(self):
        change = (
            ChangeBuilder("Add user authentication")
            .desc(
                """
                Implement OAuth2 authentication for the API.
                This will allow third-party applications to
                access the API securely.
                """
            )
            .shoulds(
                [
                    "Use PKCE for public clients",
                    "Refresh tokens after expiration",
                    "Cache access tokens efficiently",
                ]
            )
            .musts(
                [
                    "Pass all security audit checks",
                    "Support RFC 6749 compliance",
                    "Log all authentication attempts",
                ]
            )
            .approvals(["security-lead", "architect"])
            .branch("feature/oauth2-auth")
            .log_path(Path("/var/log/auth-feature.log"))
            .build()
        )

        assert change.title == "Add user authentication"
        assert change.branch == "feature/oauth2-auth"
        assert change.log_path == Path("/var/log/auth-feature.log")
        assert len(change.shoulds) == 3
        assert len(change.musts) == 3
