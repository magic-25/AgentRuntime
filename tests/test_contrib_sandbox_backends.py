import pytest

from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxUnavailableError
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend
from agent_runtime_contrib.packs.sandbox.remote import RemoteSandboxBackend
from agent_runtime_contrib.packs.sandbox.sidecar import SidecarSandboxBackend


def test_container_backend_simulation_defaults_to_network_deny(tmp_path):
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(argv=["python", "-m", "pytest"], cwd=str(tmp_path))

    result = backend.execute(spec)

    assert backend.backend_name == "container-plan-simulation"
    assert result.exit_code == 0
    assert "container plan simulation" in result.stdout
    assert "network_access=false" in result.stdout


def test_container_backend_denies_network_access(tmp_path):
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(argv=["curl", "https://example.com"], cwd=str(tmp_path), network_access=True)

    result = backend.execute(spec)

    assert result.exit_code == 126
    assert "network.denied" in result.stderr


def test_sidecar_and_remote_backends_are_unavailable_stubs(tmp_path):
    spec = SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path))

    with pytest.raises(SandboxUnavailableError, match="sidecar"):
        SidecarSandboxBackend().execute(spec)
    with pytest.raises(SandboxUnavailableError, match="remote"):
        RemoteSandboxBackend().execute(spec)
