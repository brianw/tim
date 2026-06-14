import subprocess

import pytest
from tim import MacSandboxProject
from tim.project import RunOutput
from tim.tools import _numbered, view_file, create_file, edit_file, run, ls, all_tools


@pytest.fixture
def project(tmp_path):
    return MacSandboxProject(root=tmp_path)


@pytest.fixture
def mock_project(tmp_path):
    proj = MacSandboxProject(root=tmp_path)

    def mock_run(command, timeout=1):
        result = subprocess.run(
            ["sh", "-c", command],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return RunOutput(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    proj.run = mock_run
    return proj


class TestNumbered:
    def test_basic_numbered_lines(self):
        result = _numbered(["line1\n", "line2\n", "line3\n"])
        assert result == "1\tline1\n2\tline2\n3\tline3\n"

    def test_custom_offset(self):
        result = _numbered(["a\n", "b\n"], offset=5)
        assert result == "5\ta\n6\tb\n"

    def test_empty_list(self):
        result = _numbered([])
        assert result == ""

    def test_single_line(self):
        result = _numbered(["single\n"])
        assert result == "1\tsingle\n"

    def test_custom_offset_single_line(self):
        result = _numbered(["single\n"], offset=10)
        assert result == "10\tsingle\n"

    def test_multiline_content(self):
        result = _numbered(["first\n", "second\n", "third\n"], offset=2)
        assert result == "2\tfirst\n3\tsecond\n4\tthird\n"


class TestViewFile:
    def test_normal_file_viewing(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        result = view_file(project, "test.txt")
        assert "1\tline1" in result
        assert "2\tline2" in result
        assert "3\tline3" in result

    def test_line_range(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\nline4\nline5\n")
        result = view_file(project, "test.txt", start_line=2, end_line=4)
        assert "2\tline2" in result
        assert "3\tline3" in result
        assert "4\tline4" in result
        assert "line1" not in result
        assert "line5" not in result

    def test_only_start_line(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        result = view_file(project, "test.txt", start_line=2)
        assert "2\tline2" in result
        assert "3\tline3" in result
        assert "line1" not in result

    def test_only_end_line(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        result = view_file(project, "test.txt", end_line=2)
        assert "1\tline1" in result
        assert "2\tline2" in result
        assert "line3" not in result

    def test_nonexistent_file(self, project):
        result = view_file(project, "nonexistent.txt")
        assert "Tool Error" in result
        assert "not found" in result

    def test_directory_path(self, project):
        project.path("mydir").mkdir()
        result = view_file(project, "mydir")
        assert "Tool Error" in result
        assert "directory" in result

    def test_file_with_empty_content(self, project):
        project.path("empty.txt").write_text("")
        result = view_file(project, "empty.txt")
        assert result == ""

    def test_file_with_multiple_lines(self, project):
        content = "first line\nsecond line\nthird line\nfourth line\n"
        project.path("multi.txt").write_text(content)
        result = view_file(project, "multi.txt")
        assert "1\tfirst line" in result
        assert "2\tsecond line" in result
        assert "3\tthird line" in result
        assert "4\tfourth line" in result


class TestCreateFile:
    def test_create_new_file_with_content(self, project):
        result = create_file(project, "new_file.txt", "Hello World\n")
        assert "Wrote" in result
        assert "1 lines" in result
        assert project.path("new_file.txt").read_text() == "Hello World\n"

    def test_file_that_does_not_end_with_newline(self, project):
        result = create_file(project, "no_newline.txt", "No newline at end")
        assert "1 lines" in result
        content = project.path("no_newline.txt").read_text()
        assert content == "No newline at end\n"

    def test_create_file_in_nested_directory(self, project):
        result = create_file(project, "nested/deep/file.txt", "Deep content\n")
        assert "1 lines" in result
        assert project.path("nested/deep/file.txt").read_text() == "Deep content\n"

    def test_overwrite_existing_file(self, project):
        create_file(project, "overwrite.txt", "Original content\n")
        assert project.path("overwrite.txt").read_text() == "Original content\n"
        result = create_file(project, "overwrite.txt", "New content\n")
        assert "1 lines" in result
        assert project.path("overwrite.txt").read_text() == "New content\n"

    def test_create_file_with_empty_string(self, project):
        result = create_file(project, "empty.txt", "")
        assert "0 lines" in result
        assert project.path("empty.txt").read_text() == ""

    def test_content_with_multiple_lines(self, project):
        content = "line1\nline2\nline3\n"
        result = create_file(project, "multi.txt", content)
        assert "Wrote" in result
        assert "3 lines" in result
        assert project.path("multi.txt").read_text() == content

    def test_content_without_trailing_newline_multiple_lines(self, project):
        content = "line1\nline2\nline3"
        result = create_file(project, "no_newline_multi.txt", content)
        assert "3 lines" in result
        assert project.path("no_newline_multi.txt").read_text() == "line1\nline2\nline3\n"


class TestEditFile:
    def test_replace_lines(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        edit_file(project, "test.txt", start_line=2, end_line=2, new_content="replaced\n")
        content = project.path("test.txt").read_text()
        assert "line1" in content
        assert "replaced" in content
        assert "line2" not in content
        assert "line3" in content

    def test_insert_lines(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        edit_file(project, "test.txt", start_line=2, end_line=1, new_content="inserted\n")
        content = project.path("test.txt").read_text()
        lines = content.splitlines()
        assert lines == ["line1", "inserted", "line2", "line3"]

    def test_delete_lines(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\n")
        edit_file(project, "test.txt", start_line=2, end_line=2, new_content="")
        content = project.path("test.txt").read_text()
        assert "line1" in content
        assert "line2" not in content
        assert "line3" in content

    def test_edit_nonexistent_file(self, project):
        with pytest.raises(FileNotFoundError):
            edit_file(project, "nonexistent.txt", start_line=1, end_line=1, new_content="new\n")

    def test_multiline_replacement(self, project):
        project.path("test.txt").write_text("original\n")
        replacement_text = "replaced1\nreplaced2\nreplaced3\n"
        edit_file(project, "test.txt", start_line=1, end_line=1, new_content=replacement_text)
        content = project.path("test.txt").read_text()
        assert "original" not in content
        assert "replaced1" in content
        assert "replaced2" in content
        assert "replaced3" in content

    def test_single_line_replacement(self, project):
        project.path("test.txt").write_text("old\n")
        edit_file(project, "test.txt", start_line=1, end_line=1, new_content="new\n")
        content = project.path("test.txt").read_text()
        assert content == "new\n"

    def test_edit_empty_content_file(self, project):
        project.path("test.txt").write_text("")
        edit_file(project, "test.txt", start_line=1, end_line=0, new_content="new line\n")
        content = project.path("test.txt").read_text()
        assert content == "new line\n"

    def test_delete_multiple_lines(self, project):
        project.path("test.txt").write_text("line1\nline2\nline3\nline4\nline5\n")
        edit_file(project, "test.txt", start_line=2, end_line=4, new_content="")
        content = project.path("test.txt").read_text()
        lines = content.splitlines()
        assert lines == ["line1", "line5"]

    def test_insert_at_beginning(self, project):
        project.path("test.txt").write_text("line2\nline3\n")
        edit_file(project, "test.txt", start_line=1, end_line=0, new_content="line0\n")
        content = project.path("test.txt").read_text()
        lines = content.splitlines()
        assert lines == ["line0", "line2", "line3"]

    def test_insert_at_end(self, project):
        project.path("test.txt").write_text("line1\nline2\n")
        edit_file(project, "test.txt", start_line=3, end_line=2, new_content="line3\n")
        content = project.path("test.txt").read_text()
        lines = content.splitlines()
        assert lines == ["line1", "line2", "line3"]


class TestRun:
    def test_basic_command_execution(self, mock_project):
        result = run(mock_project, "echo hello world")
        assert "hello world" in result
        assert "<returncode>0</returncode>" in result

    def test_command_with_multiline_output(self, mock_project):
        result = run(mock_project, "printf 'line1\\nline2\\nline3\\n'")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_command_with_nonzero_exit(self, mock_project):
        result = run(mock_project, "exit 42")
        assert "<returncode>42</returncode>" in result

    def test_command_with_stderr(self, mock_project):
        result = run(mock_project, "sh -c 'echo error >&2; exit 1'")
        assert "<returncode>1</returncode>" in result
        assert "error" in result


class TestLs:
    def test_list_directory_contents(self, mock_project):
        mock_project.path("file1.txt").write_text("content")
        mock_project.path("file2.txt").write_text("content")
        mock_project.path("dir1").mkdir()

        result = ls(mock_project, ".")
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "dir1" in result

    def test_list_nested_directory(self, mock_project):
        mock_project.path("subdir").mkdir()
        mock_project.path("subdir/nested.txt").write_text("content")

        result = ls(mock_project, "subdir")
        assert "nested.txt" in result


class TestAllTools:
    def test_contains_expected_tools(self):
        assert len(all_tools) == 5

        tool_names = [tool.__name__ for tool in all_tools]
        assert "view_file" in tool_names
        assert "edit_file" in tool_names
        assert "create_file" in tool_names
        assert "run" in tool_names
        assert "ls" in tool_names

    def test_is_tuple(self):
        assert isinstance(all_tools, tuple)

    def test_tools_are_callables(self):
        for tool in all_tools:
            assert callable(tool)
