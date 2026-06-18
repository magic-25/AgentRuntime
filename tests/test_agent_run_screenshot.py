from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_agent_run_screenshot_module():
    module_path = Path(__file__).resolve().parents[1] / "examples" / "agent_run_screenshot.py"
    spec = importlib.util.spec_from_file_location("agent_run_screenshot", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_agent_run_screenshot_captures_single_runtime_agent_run(tmp_path):
    module = _load_agent_run_screenshot_module()

    snapshot = module.build_agent_run_screenshot(tmp_path, provider_mode="fake")

    assert snapshot["artifact_type"] == "agent_run_screenshot"
    assert snapshot["provider_mode"] == "fake"
    assert snapshot["agent"]["agent_id"] == "runtime-screenshot-agent"
    assert snapshot["agent"]["framework"] == "openai-compatible"
    assert snapshot["prompt"] == "Call the echo tool exactly once with message 'runtime screenshot'."
    assert snapshot["transcript"]["status"] == "completed"
    assert snapshot["transcript"]["decisions"] == ["request:fake-glm", "tool_call:echo", "runtime:success", "stop"]
    assert snapshot["tool_call"]["name"] == "echo"
    assert snapshot["tool_result"]["status"] == "success"
    assert snapshot["tool_result"]["output"] == {"message": "runtime screenshot"}
    assert snapshot["governance"]["policy"]["decision"] == "allow"
    assert snapshot["governance"]["audit"]["status"] == "committed"
    assert snapshot["trace"]["contains"]["agent_run"] is True
    assert snapshot["trace"]["contains"]["tool_call"] is True
    assert snapshot["trace"]["contains"]["policy_evaluation"] is True
    assert "AgentRegistered" in snapshot["audit"]["events"]
    assert "AgentRunFinished" in snapshot["audit"]["events"]

    json_path = tmp_path / "real-provider-agent-run.json"
    html_path = tmp_path / "real-provider-agent-run.html"
    screenshot_path = tmp_path / "real-provider-agent-run.png"
    assert json.loads(json_path.read_text(encoding="utf-8"))["tool_result"] == snapshot["tool_result"]
    assert "Provider Agent Run" in html_path.read_text(encoding="utf-8")
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0
