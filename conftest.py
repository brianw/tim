from pathlib import Path
import shutil
import subprocess
import tempfile
import pytest
from tim import MacSandboxProject


EVAL_PROJECTS = Path(__file__).parent / "eval-projects"


def pytest_addoption(parser):
    parser.addoption("--evals", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if config.getoption("--evals"):
        items[:] = [item for item in items if item.path.name.endswith("_eval.py")]
    else:
        items[:] = [item for item in items if not item.path.name.endswith("_eval.py")]


@pytest.fixture
def project_empty():
    with tempfile.TemporaryDirectory() as tempdir:
        subprocess.run(
            ["uv", "init", "evalproject"],
            check=True,
            cwd=tempdir,
        )
        yield MacSandboxProject(Path(tempdir) / "evalproject")


@pytest.fixture
def project_jsonprinter():
    name = "jsonprinter"
    with tempfile.TemporaryDirectory() as tempdir:
        project_root = Path(tempdir) / name
        shutil.copytree(EVAL_PROJECTS / name, project_root)
        yield MacSandboxProject(project_root)
