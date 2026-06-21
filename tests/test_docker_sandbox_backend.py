import subprocess

import pytest

from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxUnavailableError, SandboxViolationError
from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend


class RecordingDockerRun:
    def __init__(self, stdout: str = "ok\n") -> None:
        self.stdout = stdout
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout=self.stdout, stderr="")


def test_docker_backend_runs_command_with_strong_default_flags(tmp_path):
    runner = RecordingDockerRun(stdout="hello\n")
    backend = DockerSandboxBackend(image="python:3.12-slim", run=runner)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = backend.execute(
        SandboxCommandSpec(
            argv=["python", "-c", "print('hello')"],
            cwd=str(tmp_path),
            env={"VISIBLE": "1", "SECRET": "nope"},
            env_allowlist=["VISIBLE"],
            write_paths=[str(out_dir)],
        )
    )

    docker_argv, kwargs = runner.calls[0]
    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert docker_argv[:3] == ["docker", "run", "--rm"]
    assert "--network" in docker_argv
    assert "none" in docker_argv
    assert "--read-only" in docker_argv
    assert "--cap-drop" in docker_argv
    assert "ALL" in docker_argv
    assert "--security-opt" in docker_argv
    assert "no-new-privileges" in docker_argv
    assert "--pids-limit" in docker_argv
    assert "--cpus" in docker_argv
    assert "--memory" in docker_argv
    assert f"{tmp_path}:/workspace:ro" in docker_argv
    assert f"{out_dir}:/workspace/out:rw" in docker_argv
    assert "--env" in docker_argv
    assert "VISIBLE" in docker_argv
    assert "VISIBLE=1" not in docker_argv
    assert "SECRET=nope" not in docker_argv
    assert kwargs["env"]["VISIBLE"] == "1"
    assert "SECRET" not in kwargs["env"]
    assert docker_argv[-4:] == ["python:3.12-slim", "python", "-c", "print('hello')"]
    assert kwargs["timeout"] == 30


def test_docker_backend_denies_network_before_calling_docker(tmp_path):
    runner = RecordingDockerRun()
    backend = DockerSandboxBackend(run=runner)

    with pytest.raises(SandboxViolationError, match="network.denied"):
        backend.execute(SandboxCommandSpec(argv=["curl", "https://example.com"], cwd=str(tmp_path), network_access=True))
    assert runner.calls == []


def test_docker_backend_denies_secret_like_allowlisted_env_before_calling_docker(tmp_path):
    runner = RecordingDockerRun()
    backend = DockerSandboxBackend(run=runner)

    with pytest.raises(SandboxViolationError, match="env.secret_denied"):
        backend.execute(
            SandboxCommandSpec(
                argv=["python", "-V"],
                cwd=str(tmp_path),
                env={"API_KEY": "secret"},
                env_allowlist=["API_KEY"],
            )
        )
    assert runner.calls == []


def test_docker_backend_raises_unavailable_when_docker_binary_is_missing(tmp_path):
    def missing_docker(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("docker")

    backend = DockerSandboxBackend(run=missing_docker)

    with pytest.raises(SandboxUnavailableError, match="docker.unavailable"):
        backend.execute(SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path)))


def test_docker_backend_maps_timeout_to_process_result(tmp_path):
    def timeout(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, timeout=kwargs["timeout"], output="partial", stderr="late")

    backend = DockerSandboxBackend(run=timeout)

    result = backend.execute(SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path), timeout_ms=100))

    assert result.exit_code == 124
    assert result.stdout == "partial"
    assert "docker.timeout" in result.stderr


def test_docker_backend_truncates_output_to_spec_limits(tmp_path):
    runner = RecordingDockerRun(stdout="abcdef")
    backend = DockerSandboxBackend(run=runner)

    result = backend.execute(SandboxCommandSpec(argv=["python", "-V"], cwd=str(tmp_path), stdout_limit_bytes=3))

    assert result.stdout == "abc"
