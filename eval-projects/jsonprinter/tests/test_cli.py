from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_json():
    return {"name": "test", "value": 42, "nested": {"key": "value"}}


@pytest.fixture
def sample_json_str(sample_json):
    return json.dumps(sample_json)


def _normalize_output(output):
    """Normalize output by stripping extra trailing newlines."""
    return output.rstrip('\n') + '\n'


class TestReformatDefaultStdin:
    """Test default behavior with stdin input (4-space indent)."""

    def test_default_4_space_indent_from_stdin(self, runner, sample_json_str):
        """Test that reformat with stdin uses 4-space indentation by default."""
        result = runner.invoke(cli, ["reformat"], input=sample_json_str)
        assert result.exit_code == 0
        # Default indent is 4 spaces
        expected = json.dumps(json.loads(sample_json_str), indent=4, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_default_indent_preserves_json_content(self, runner, sample_json_str):
        """Test that default reformat preserves the JSON content."""
        result = runner.invoke(cli, ["reformat"], input=sample_json_str)
        assert result.exit_code == 0
        # Verify output is valid JSON
        output_json = json.loads(result.output)
        assert output_json == json.loads(sample_json_str)

    def test_default_indent_with_nested_objects(self, runner):
        """Test default behavior with deeply nested JSON."""
        nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "deep": True
                    }
                }
            }
        }
        result = runner.invoke(cli, ["reformat"], input=json.dumps(nested))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == nested
        # Verify indentation is 4 spaces
        lines = result.output.split("\n")
        for line in lines:
            if line.strip() and line != lines[-1]:
                leading_spaces = len(line) - len(line.lstrip())
                assert leading_spaces % 4 == 0, f"Expected 4-space indent, got {leading_spaces} spaces: {repr(line)}"

    def test_default_indent_with_arrays(self, runner):
        """Test default behavior with arrays."""
        data = {"items": [1, 2, 3], "mixed": ["a", 1, True, None]}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == data

    def test_default_output_ends_with_newline(self, runner, sample_json_str):
        """Test that default output ends with a newline."""
        result = runner.invoke(cli, ["reformat"], input=sample_json_str)
        assert result.exit_code == 0
        assert result.output.endswith("\n")

    def test_default_stdin_empty_json_object(self, runner):
        """Test default behavior with empty JSON object."""
        result = runner.invoke(cli, ["reformat"], input="{}")
        assert result.exit_code == 0
        assert json.loads(result.output) == {}

    def test_default_stdin_empty_json_array(self, runner):
        """Test default behavior with empty JSON array."""
        result = runner.invoke(cli, ["reformat"], input="[]")
        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_default_stdin_json_primitives(self, runner):
        """Test default behavior with JSON primitive values."""
        for value in [42, 3.14, "hello", True, False, None]:
            result = runner.invoke(cli, ["reformat"], input=json.dumps(value))
            assert result.exit_code == 0
            assert json.loads(result.output) == value

    def test_default_stdin_unicode_characters(self, runner):
        """Test default behavior preserves unicode characters."""
        data = {"emoji": "😀", "chinese": "中文", "russian": "Привет"}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        assert "😀" in result.output
        assert "中文" in result.output
        assert "Привет" in result.output


class TestReformatFileInput:
    """Test file input functionality."""

    def test_reformat_from_file(self, runner, tmp_path, sample_json):
        """Test reformat reads from a file path argument."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json))
        result = runner.invoke(cli, ["reformat", str(input_file)])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json == sample_json

    def test_reformat_file_preserves_indent(self, runner, tmp_path, sample_json):
        """Test reformat with file input uses 4-space default indent."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json, indent=2))
        result = runner.invoke(cli, ["reformat", str(input_file)])
        assert result.exit_code == 0
        # Should use 4-space indent by default
        expected = json.dumps(sample_json, indent=4, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_reformat_file_complex_nested(self, runner, tmp_path):
        """Test reformat with complex nested file input."""
        complex_data = {
            "users": [
                {"id": 1, "name": "Alice", "active": True},
                {"id": 2, "name": "Bob", "active": False}
            ],
            "metadata": {
                "version": "1.0",
                "tags": ["beta", "test"]
            }
        }
        input_file = tmp_path / "complex.json"
        input_file.write_text(json.dumps(complex_data))
        result = runner.invoke(cli, ["reformat", str(input_file)])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == complex_data

    def test_reformat_file_minified_json(self, runner, tmp_path, sample_json):
        """Test reformat expands minified JSON from file."""
        input_file = tmp_path / "minified.json"
        input_file.write_text(json.dumps(sample_json, separators=(",", ":")))
        result = runner.invoke(cli, ["reformat", str(input_file)])
        assert result.exit_code == 0
        # Should have newlines and spaces (expanded format)
        assert "\n" in result.output

    def test_reformat_file_preserves_whitespace_strings(self, runner, tmp_path):
        """Test file input preserves strings with whitespace."""
        data = {"message": "  spaces  ", "quote": "He said \"hello\""}
        input_file = tmp_path / "whitespace.json"
        input_file.write_text(json.dumps(data))
        result = runner.invoke(cli, ["reformat", str(input_file)])
        assert result.exit_code == 0
        assert "spaces" in result.output
        assert "hello" in result.output


class TestReformatCustomIndent:
    """Test custom indent values via --indent/-i option."""

    def test_indent_2_spaces(self, runner, sample_json_str):
        """Test reformat with --indent 2."""
        result = runner.invoke(cli, ["reformat", "--indent", "2"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=2, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_2_spaces_short_option(self, runner, sample_json_str):
        """Test reformat with -i 2."""
        result = runner.invoke(cli, ["reformat", "-i", "2"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=2, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_1_space(self, runner, sample_json_str):
        """Test reformat with --indent 1."""
        result = runner.invoke(cli, ["reformat", "--indent", "1"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=1, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_8_spaces(self, runner, sample_json_str):
        """Test reformat with --indent 8."""
        result = runner.invoke(cli, ["reformat", "--indent", "8"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=8, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_0_flat(self, runner, sample_json_str):
        """Test reformat with --indent 0 (flat with newlines)."""
        result = runner.invoke(cli, ["reformat", "--indent", "0"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=0, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_preserves_content(self, runner, sample_json):
        """Test that custom indent preserves JSON content."""
        result = runner.invoke(cli, ["reformat", "--indent", "2"], input=json.dumps(sample_json))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == sample_json

    def test_indent_with_file_input(self, runner, tmp_path, sample_json):
        """Test custom indent works with file input."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json))
        result = runner.invoke(cli, ["reformat", str(input_file), "-i", "2"])
        assert result.exit_code == 0
        expected = json.dumps(sample_json, indent=2, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_indent_with_nested_data(self, runner, sample_json_str):
        """Test custom indent with deeply nested data."""
        nested = json.loads(sample_json_str)
        nested["deep"] = {"level1": {"level2": {"level3": {"deep": True}}}}
        indent = 2
        result = runner.invoke(cli, ["reformat", "-i", str(indent)], input=json.dumps(nested))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == nested
        # Verify correct indentation depth
        lines = result.output.split("\n")
        for line in lines:
            if line.strip() and line != lines[-1]:
                leading_spaces = len(line) - len(line.lstrip())
                assert leading_spaces % indent == 0

    def test_indent_with_large_indent_value(self, runner, sample_json_str):
        """Test reformat with large indent value."""
        result = runner.invoke(cli, ["reformat", "--indent", "16"], input=sample_json_str)
        assert result.exit_code == 0
        expected = json.dumps(json.loads(sample_json_str), indent=16, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected


class TestReformatOutputToFile:
    """Test output to file via --output/-o option."""

    def test_output_to_file(self, runner, tmp_path, sample_json_str):
        """Test reformat with --output flag writes to file."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        assert output_file.exists()
        output_content = output_file.read_text()
        expected = json.dumps(json.loads(sample_json_str), indent=4, ensure_ascii=False) + "\n"
        assert output_content == expected

    def test_output_to_file_short_option(self, runner, tmp_path, sample_json_str):
        """Test reformat with -o flag writes to file."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        assert output_file.exists()
        output_content = output_file.read_text()
        expected = json.dumps(json.loads(sample_json_str), indent=4, ensure_ascii=False) + "\n"
        assert output_content == expected

    def test_output_to_file_no_stdout(self, runner, tmp_path, sample_json_str):
        """Test that reformat with --output does not print to stdout."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        # Output should go to file, not stdout
        assert result.output == ""

    def test_output_to_file_creates_directory(self, runner, tmp_path, sample_json_str):
        """Test that output file in existing directory works."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        output_file = subdir / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        assert output_file.exists()

    def test_output_file_preserves_json_content(self, runner, tmp_path, sample_json):
        """Test that output file contains valid JSON."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=json.dumps(sample_json))
        assert result.exit_code == 0
        output = json.loads(output_file.read_text())
        assert output == sample_json

    def test_output_file_replaces_existing(self, runner, tmp_path, sample_json_str):
        """Test that reformat overwrites existing output file."""
        output_file = tmp_path / "existing.json"
        output_file.write_text('{"old": "data"}')
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        output = json.loads(output_file.read_text())
        expected = json.loads(sample_json_str)
        assert output == expected
        assert "old" not in output

    def test_output_file_with_complex_json(self, runner, tmp_path):
        """Test output file with complex nested JSON."""
        complex_data = {
            "string": "test",
            "numbers": {"int": 42, "float": 3.14},
            "array": [1, 2, 3],
            "nested": {"deep": {"deeper": True}}
        }
        output_file = tmp_path / "complex.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=json.dumps(complex_data))
        assert result.exit_code == 0
        output = json.loads(output_file.read_text())
        assert output == complex_data


class TestReformatErrorHandling:
    """Test error handling for invalid JSON."""

    def test_invalid_json_syntax(self, runner):
        """Test that invalid JSON syntax produces an error."""
        result = runner.invoke(cli, ["reformat"], input="{invalid json}")
        assert result.exit_code != 0
        # CliRunner captures exceptions - check result exception
        assert result.exception is not None

    def test_invalid_json_missing_brace(self, runner):
        """Test error handling for missing closing brace."""
        result = runner.invoke(cli, ["reformat"], input='{"key": "value"')
        assert result.exit_code != 0

    def test_invalid_json_trailing_comma(self, runner):
        """Test error handling for trailing comma."""
        result = runner.invoke(cli, ["reformat"], input='{"key": "value",}')
        assert result.exit_code != 0

    def test_invalid_json_single_quotes(self, runner):
        """Test error handling for single-quoted strings."""
        result = runner.invoke(cli, ["reformat"], input="{'key': 'value'}")
        assert result.exit_code != 0

    def test_invalid_json_unquoted_key(self, runner):
        """Test error handling for unquoted keys."""
        result = runner.invoke(cli, ["reformat"], input='{key: "value"}')
        assert result.exit_code != 0

    def test_invalid_json_not_valid_json_anywhere(self, runner):
        """Test error handling for non-JSON text."""
        result = runner.invoke(cli, ["reformat"], input="This is not JSON at all!")
        assert result.exit_code != 0

    def test_empty_input(self, runner):
        """Test error handling for empty input."""
        result = runner.invoke(cli, ["reformat"], input="")
        assert result.exit_code != 0

    def test_invalid_json_with_file_input(self, runner, tmp_path):
        """Test error handling for invalid JSON in file."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{this is not valid json}")
        result = runner.invoke(cli, ["reformat", str(invalid_file)])
        assert result.exit_code != 0

    def test_invalid_json_with_custom_indent(self, runner):
        """Test error handling for invalid JSON even with valid indent option."""
        result = runner.invoke(cli, ["reformat", "--indent", "2"], input="{bad json}")
        assert result.exit_code != 0

    def test_invalid_json_with_output_file(self, runner, tmp_path):
        """Test that output file is not created on invalid JSON."""
        output_file = tmp_path / "should_not_exist.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input="{invalid}")
        assert result.exit_code != 0
        assert not output_file.exists()


class TestReformatCombinedOptions:
    """Test combined options (stdin + output file, file + custom indent, etc.)."""

    def test_stdin_with_output_file(self, runner, tmp_path, sample_json_str):
        """Test stdin input with output file."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", "-o", str(output_file)], input=sample_json_str)
        assert result.exit_code == 0
        assert output_file.exists()
        output = json.loads(output_file.read_text())
        expected = json.loads(sample_json_str)
        assert output == expected
        assert result.output == ""  # No stdout

    def test_file_input_with_custom_indent(self, runner, tmp_path, sample_json):
        """Test file input with custom indent."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json, indent=2))
        output_file = tmp_path / "output.json"
        result = runner.invoke(cli, ["reformat", str(input_file), "-i", "2", "-o", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()
        expected = json.dumps(sample_json, indent=2, ensure_ascii=False) + "\n"
        assert output_file.read_text() == expected
        assert result.output == ""

    def test_file_input_with_custom_indent_no_output_file(self, runner, tmp_path, sample_json):
        """Test file input with custom indent to stdout."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json, indent=2))
        result = runner.invoke(cli, ["reformat", str(input_file), "--indent", "8"])
        assert result.exit_code == 0
        expected = json.dumps(sample_json, indent=8, ensure_ascii=False) + "\n"
        assert _normalize_output(result.output) == expected

    def test_all_options_together(self, runner, tmp_path, sample_json):
        """Test all options together: file input + custom indent + output file."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json, indent=2))
        output_file = tmp_path / "output.json"
        result = runner.invoke(
            cli,
            ["reformat", str(input_file), "-i", "6", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        expected = json.dumps(sample_json, indent=6, ensure_ascii=False) + "\n"
        assert output_file.read_text() == expected

    def test_stdin_with_output_and_indent(self, runner, tmp_path, sample_json_str):
        """Test stdin with output file and custom indent."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(
            cli,
            ["reformat", "-i", "2", "-o", str(output_file)],
            input=sample_json_str
        )
        assert result.exit_code == 0
        assert output_file.exists()
        expected = json.dumps(json.loads(sample_json_str), indent=2, ensure_ascii=False) + "\n"
        assert output_file.read_text() == expected
        assert result.output == ""

    def test_long_options_combined(self, runner, tmp_path, sample_json_str):
        """Test all long options combined."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(
            cli,
            ["reformat", "--indent", "4", "--output", str(output_file)],
            input=sample_json_str
        )
        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text() == json.dumps(
            json.loads(sample_json_str), indent=4, ensure_ascii=False
        ) + "\n"

    def test_mixed_short_long_options(self, runner, tmp_path, sample_json_str):
        """Test mixing short and long options."""
        output_file = tmp_path / "output.json"
        result = runner.invoke(
            cli,
            ["reformat", "-i", "2", "--output", str(output_file)],
            input=sample_json_str
        )
        assert result.exit_code == 0
        assert output_file.exists()
        expected = json.dumps(json.loads(sample_json_str), indent=2, ensure_ascii=False) + "\n"
        assert output_file.read_text() == expected

    def test_file_input_with_output_and_different_indent(self, runner, tmp_path, sample_json):
        """Test file input with output file but different indent."""
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(sample_json, indent=2))
        output_file = tmp_path / "output.json"
        result = runner.invoke(
            cli,
            ["reformat", str(input_file), "-i", "2", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        output = json.loads(output_file.read_text())
        assert output == sample_json
        # Verify 2-space indent in output
        expected = json.dumps(sample_json, indent=2, ensure_ascii=False) + "\n"
        assert output_file.read_text() == expected


class TestReformatEdgeCases:
    """Test edge cases and additional scenarios."""

    def test_ensure_ascii_default(self, runner):
        """Test that ensure_ascii defaults to False."""
        data = {"emoji": "😀🎉"}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data, ensure_ascii=False))
        assert result.exit_code == 0
        # Emoji should appear as-is, not as unicode escape sequences
        assert "😀" in result.output
        assert "🎉" in result.output

    def test_ensure_ascii_false_with_unicode(self, runner):
        """Test unicode characters are preserved in output."""
        data = {
            "chinese": "中文测试",
            "japanese": "日本語",
            "korean": "한국어",
            "arabic": "العربية",
            "hebrew": "עברית"
        }
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        for key in data:
            assert data[key] in result.output

    def test_large_json(self, runner):
        """Test handling of large JSON."""
        large_data = {f"key_{i}": f"value_{i}" for i in range(100)}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(large_data))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output) == 100
        assert output == large_data

    def test_json_with_null_values(self, runner):
        """Test JSON with null values."""
        data = {"null_value": None, "another": "test"}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        assert "null" in result.output

    def test_json_with_0_and_empty_strings(self, runner):
        """Test JSON with falsy values."""
        data = {"zero": 0, "empty": "", "false": False, "nested": {"also_zero": 0}}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == data

    def test_json_with_boolean_values(self, runner):
        """Test JSON with boolean values."""
        data = {"bool_true": True, "bool_false": False}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        assert "true" in result.output
        assert "false" in result.output
        # Verify the output parses correctly with boolean values
        output = json.loads(result.output)
        assert output["bool_true"] is True
        assert output["bool_false"] is False

    def test_json_special_characters_in_strings(self, runner):
        """Test JSON with special characters in string values."""
        data = {
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
            "backslash": "path\\to\\file",
            "quote": "say \"hello\"",
            "unicode_escape": "\u0041"  # Should be "A"
        }
        result = runner.invoke(cli, ["reformat"], input=json.dumps(data))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == data

    def test_very_deep_nesting(self, runner):
        """Test very deeply nested JSON structure."""
        deep = {}
        current = deep
        for i in range(50):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["value"] = True
        result = runner.invoke(cli, ["reformat"], input=json.dumps(deep))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == deep

    def test_very_wide_object(self, runner):
        """Test very wide JSON object with many keys."""
        wide = {f"key_{i}": f"value_{i}" for i in range(50)}
        result = runner.invoke(cli, ["reformat"], input=json.dumps(wide))
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output == wide

    def test_cli_help(self, runner):
        """Test that reformat command help works."""
        result = runner.invoke(cli, ["reformat", "--help"])
        assert result.exit_code == 0
        assert "--indent" in result.output
        assert "--output" in result.output

    def test_cli_group_help(self, runner):
        """Test that CLI group help works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "reformat" in result.output
        assert "view" in result.output
