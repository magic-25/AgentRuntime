import pytest

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxUnavailableError
from agent_runtime_contrib.packs.sandbox.sidecar import SidecarSandboxBackend


class RecordingSidecarClient:
    def __init__(self):
        self.calls = []

    def run(self, spec):
        self.calls.append(spec)
        return ProcessResult(exit_code=0, stdout="sidecar-ok", stderr="")


class TimeoutSidecarClient:
    def run(self, spec):
        raise TimeoutError("sidecar timeout")


def test_sidecar_backend_is_minimal_runnable_with_client(tmp_path):
    client = RecordingSidecarClient()
    backend = SidecarSandboxBackend(client=client, backend_version="1.2-test")
    spec = SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path))

    result = backend.execute(spec)

    assert backend.backend_name == "sidecar"
    assert backend.backend_version == "1.2-test"
    assert result.stdout == "sidecar-ok"
    assert client.calls == [spec]


def test_sidecar_backend_fails_closed_when_unavailable_or_timeout(tmp_path):
    spec = SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path))

    with pytest.raises(SandboxUnavailableError, match="sandbox.unavailable"):
        SidecarSandboxBackend().execute(spec)

    with pytest.raises(SandboxUnavailableError, match="sandbox.timeout"):
        SidecarSandboxBackend(client=TimeoutSidecarClient()).execute(spec)
