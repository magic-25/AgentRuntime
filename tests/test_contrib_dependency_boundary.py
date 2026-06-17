import importlib
import sys
import tomllib
from pathlib import Path


def test_importing_agent_runtime_core_does_not_import_contrib():
    sys.modules.pop("agent_runtime", None)
    sys.modules.pop("agent_runtime_contrib", None)

    importlib.import_module("agent_runtime")

    assert "agent_runtime_contrib" not in sys.modules


def test_pyproject_defines_contrib_optional_dependency_groups():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    optional = pyproject["project"]["optional-dependencies"]

    assert "contrib-adapters" in optional
    assert "contrib-sandbox" in optional
    assert "pilot-code-ci" in optional
    assert "real-agents" in optional
