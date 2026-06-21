from pathlib import Path

from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend


def test_docker_backend_remains_preview_until_stable_candidate_gate_is_met():
    roadmap = Path("ROADMAP.md").read_text(encoding="utf-8")

    assert DockerSandboxBackend.support_level == "preview"
    assert "Docker sandbox backend stable candidate gate" in roadmap
    assert "host security baseline" in roadmap
    assert "trusted image chain" in roadmap
    assert "append-only audit export" in roadmap
    assert "design partner staging evidence" in roadmap
