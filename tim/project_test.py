import pytest
from pathlib import Path
from tim.project import MacSandboxProject
import uuid


@pytest.fixture
def project(tmp_path):
    return MacSandboxProject(root=tmp_path)


def test_run_returns_stdout(project):
    result = project.run("echo hello", timeout=5)
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"


def test_run_returns_nonzero_exit(project):
    result = project.run("sh -c 'exit 42'", timeout=5)
    assert result.returncode == 42


def test_run_write_inside_root_allowed(project):
    target = project.root / "output.txt"
    result = project.run(f"sh -c 'echo ok > {target}'", timeout=5)
    assert result.returncode == 0
    assert target.read_text().strip() == "ok"


def test_run_write_outside_root_denied(project):
    # /private/var/tmp is world-writable on macOS but is NOT in the sandbox allowlist
    outside = Path(f"/private/var/tmp/sandbox_escape_test_{uuid.uuid4().hex}.txt")
    outside.unlink(missing_ok=True)
    try:
        project.run(f"sh -c 'echo bad > {outside}'", timeout=5)
        assert not outside.exists(), "sandbox should have blocked the write"
    finally:
        outside.unlink(missing_ok=True)


def test_run_timeout(project):
    result = project.run("sleep 60", timeout=1)
    assert result.returncode == -1
    assert "timeout" in result.stdout.lower()
