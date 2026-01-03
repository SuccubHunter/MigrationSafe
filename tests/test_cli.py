"""Tests for CLI interface."""

import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from migsafe.cli import analyze_files, cli, find_migration_files, get_formatter, has_critical_issues
from migsafe.models import IssueSeverity


def test_cli_help():
    """Test CLI help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "migsafe" in result.output
    assert "analyze" in result.output
    assert "lint" in result.output


def test_cli_version():
    """Test version output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "0.4.0" in result.output


def test_analyze_command_help():
    """Test analyze command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "analyze" in result.output.lower()


def test_lint_command_help():
    """Test lint command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--help"])

    assert result.exit_code == 0
    assert "lint" in result.output.lower()


def test_analyze_single_file():
    """Test analyzing single migration file."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path])

        assert result.exit_code == 0
        assert "migration" in result.output.lower()
    finally:
        os.unlink(temp_path)


def test_analyze_file_with_critical_issue():
    """Test analyzing file with critical issue."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path])

        assert result.exit_code == 0  # Without --exit-code should not fail
        assert "CRITICAL" in result.output or "critical" in result.output.lower()
    finally:
        os.unlink(temp_path)


def test_analyze_with_exit_code():
    """Test analysis with --exit-code for critical issues."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--exit-code"])

        assert result.exit_code == 1  # Should return 1 for critical issues
    finally:
        os.unlink(temp_path)


def test_analyze_with_exit_code_no_issues():
    """Test analysis with --exit-code without critical issues."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=True)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--exit-code"])

        assert result.exit_code == 0  # Should return 0 without critical issues
    finally:
        os.unlink(temp_path)


def test_analyze_json_format():
    """Test analysis with JSON format."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--format", "json"])

        assert result.exit_code == 0
        assert "version" in result.output
        assert "migrations" in result.output
        # Check that this is valid JSON
        import json

        json.loads(result.output)
    finally:
        os.unlink(temp_path)


def test_analyze_html_format():
    """Test analysis with HTML format."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--format", "html"])

        assert result.exit_code == 0
        assert "<!DOCTYPE html>" in result.output
        assert "html" in result.output.lower()
    finally:
        os.unlink(temp_path)


def test_analyze_junit_format():
    """Test analysis with JUnit XML format."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--format", "junit"])

        assert result.exit_code == 0
        assert "<?xml" in result.output
        assert "testsuites" in result.output
    finally:
        os.unlink(temp_path)


def test_analyze_sarif_format():
    """Test analysis with SARIF format."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--format", "sarif"])

        assert result.exit_code == 0
        # Check that this is valid JSON and contains SARIF structure
        import json

        sarif_data = json.loads(result.output)
        assert sarif_data["version"] == "2.1.0"
        assert "runs" in sarif_data
        assert len(sarif_data["runs"]) > 0
        assert "tool" in sarif_data["runs"][0]
    finally:
        os.unlink(temp_path)


def test_analyze_output_to_file():
    """Test saving result to file."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    output_file = temp_path + ".output"

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--output", output_file])

        assert result.exit_code == 0
        assert os.path.exists(output_file)
        assert "saved" in result.output.lower()

        # Check file contents
        content = Path(output_file).read_text(encoding="utf-8")
        assert len(content) > 0
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if os.path.exists(output_file):
            os.unlink(output_file)


def test_analyze_severity_filter():
    """Test filtering by severity level."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=False)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--severity", "critical"])

        assert result.exit_code == 0
        # Should only have critical issues
        assert "CRITICAL" in result.output or "critical" in result.output.lower()
    finally:
        os.unlink(temp_path)


def test_analyze_quiet_mode():
    """Test quiet mode."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--quiet"])

        assert result.exit_code == 0
        # In quiet mode should have minimal output
    finally:
        os.unlink(temp_path)


def test_analyze_verbose_mode():
    """Test verbose mode."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--verbose"])

        assert result.exit_code == 0
    finally:
        os.unlink(temp_path)


def test_analyze_no_color():
    """Test disabling colors."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--no-color"])

        assert result.exit_code == 0
        # ANSI codes should not be present
        assert "\033[" not in result.output
    finally:
        os.unlink(temp_path)


def test_analyze_directory():
    """Test analyzing directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create migration file
        migration_file = Path(tmpdir) / "001_test.py"
        migration_file.write_text("""
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", tmpdir])

        assert result.exit_code == 0


def test_analyze_multiple_files():
    """Test analyzing multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create several migration files
        files = []
        for i in range(3):
            migration_file = Path(tmpdir) / f"00{i}_test.py"
            migration_file.write_text("""
def upgrade():
    op.add_column("users", sa.Column("field", sa.String(), nullable=True))
""")
            files.append(str(migration_file))

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze"] + files)

        assert result.exit_code == 0


def test_analyze_nonexistent_file():
    """Test analyzing non-existent file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "/nonexistent/file.py"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_analyze_no_files_found():
    """Test analysis without found files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory without .py files
        (Path(tmpdir) / "test.txt").write_text("test")

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", tmpdir])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


def test_lint_command():
    """Test lint command."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", temp_path])

        # lint should always return 1 for critical issues
        assert result.exit_code == 1
    finally:
        os.unlink(temp_path)


def test_lint_command_no_issues():
    """Test lint command without issues."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=True)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", temp_path])

        assert result.exit_code == 0
    finally:
        os.unlink(temp_path)


def test_find_migration_files():
    """Test function for finding migration files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files
        py_file = Path(tmpdir) / "test.py"
        py_file.write_text("# test")

        txt_file = Path(tmpdir) / "test.txt"
        txt_file.write_text("test")

        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        subdir_py = subdir / "migration.py"
        subdir_py.write_text("# migration")

        # Test with file
        files = find_migration_files([py_file])
        assert len(files) == 1
        assert py_file in files

        # Test with directory
        files = find_migration_files([Path(tmpdir)])
        assert len(files) == 2  # test.py and subdir/migration.py

        # Test with non-existent path
        files = find_migration_files([Path("/nonexistent")])
        assert len(files) == 0


def test_analyze_files_function():
    """Test analyze_files function."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = Path(f.name)

    try:
        results, error_count = analyze_files([temp_path])

        assert len(results) == 1
        assert error_count == 0
        file_path, result = results[0]
        assert file_path == temp_path
        assert len(result.operations) == 1
        assert len(result.issues) > 0
    finally:
        os.unlink(temp_path)


def test_get_formatter():
    """Test get_formatter function."""
    from migsafe.formatters import HtmlFormatter, JsonFormatter, JUnitFormatter, TextFormatter

    formatter = get_formatter("text", None, False, False, False)
    assert isinstance(formatter, TextFormatter)

    formatter = get_formatter("json", None, False, False, False)
    assert isinstance(formatter, JsonFormatter)

    formatter = get_formatter("html", None, False, False, False)
    assert isinstance(formatter, HtmlFormatter)

    formatter = get_formatter("junit", None, False, False, False)
    assert isinstance(formatter, JUnitFormatter)


def test_get_formatter_invalid():
    """Test get_formatter with invalid format."""
    from click import BadParameter

    with pytest.raises(BadParameter):
        get_formatter("invalid", None, False, False, False)


def test_has_critical_issues():
    """Test has_critical_issues function."""
    from migsafe.base import AnalyzerResult
    from migsafe.models import Issue, IssueType

    # Result with critical issues
    result_with_critical = AnalyzerResult(
        operations=[],
        issues=[
            Issue(
                severity=IssueSeverity.CRITICAL,
                type=IssueType.ADD_COLUMN_NOT_NULL,
                message="Test",
                operation_index=0,
                recommendation="Test",
                table="users",
                column="email",
            )
        ],
    )

    assert has_critical_issues([(Path("test.py"), result_with_critical)]) is True

    # Result without critical issues
    result_without_critical = AnalyzerResult(
        operations=[],
        issues=[
            Issue(
                severity=IssueSeverity.WARNING,
                type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
                message="Test",
                operation_index=0,
                recommendation="Test",
                table="users",
                index="ix_test",
            )
        ],
    )

    assert has_critical_issues([(Path("test.py"), result_without_critical)]) is False


def test_analyze_exclude_pattern():
    """Test excluding files by pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files
        included = Path(tmpdir) / "001_migration.py"
        included.write_text("""
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
""")

        excluded = Path(tmpdir) / "002_excluded.py"
        excluded.write_text("""
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", tmpdir, "--exclude", "*excluded*"])

        assert result.exit_code == 0
        # Excluded file should not be in output
        assert "002_excluded" not in result.output


def test_analyze_with_config():
    """Test analysis with config file."""
    migration_content = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(migration_content)
        temp_path = f.name

    # Create configuration file
    config_content = {"format": "json", "no_color": True, "verbose": False}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json

        json.dump(config_content, f)
        config_path = f.name

    try:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", temp_path, "--config", config_path])

        assert result.exit_code == 0
        # Check that format from config is applied (should be JSON)
        import json

        json.loads(result.output)  # Should be valid JSON
    finally:
        os.unlink(temp_path)
        os.unlink(config_path)
