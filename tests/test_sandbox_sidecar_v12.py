import pytest

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxExecutionPlan, SandboxUnavailableError, SandboxViolationError
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
    assert len(client.calls) == 1
    assert isinstance(client.calls[0], SandboxExecutionPlan)
    assert client.calls[0].cwd == tmp_path.resolve()


def test_sidecar_backend_fails_closed_when_unavailable_or_timeout(tmp_path):
    spec = SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path))

    with pytest.raises(SandboxUnavailableError, match="sandbox.unavailable"):
        SidecarSandboxBackend().execute(spec)

    with pytest.raises(SandboxUnavailableError, match="sandbox.timeout"):
        SidecarSandboxBackend(client=TimeoutSidecarClient()).execute(spec)


def test_sidecar_backend_validates_spec_before_client_receives_it(tmp_path):
    client = RecordingSidecarClient()
    backend = SidecarSandboxBackend(client=client)

    with pytest.raises(SandboxViolationError, match="network.denied"):
        backend.execute(SandboxCommandSpec(argv=["curl", "https://example.com"], cwd=str(tmp_path), network_access=True))

    with pytest.raises(SandboxViolationError, match="env.secret_denied"):
        backend.execute(
            SandboxCommandSpec(
                argv=["python", "-V"],
                cwd=str(tmp_path),
                env={"SECRET_TOKEN": "secret"},
                env_allowlist=["SECRET_TOKEN"],
            )
        )

    assert client.calls == []
