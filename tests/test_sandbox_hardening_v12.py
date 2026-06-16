from pathlib import Path

import pytest

from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxResourceLimits, SandboxViolationError
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend


def test_container_backend_rejects_overlapping_read_and_write_mounts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["python", "-m", "pytest"],
        cwd=str(repo),
        read_paths=[str(repo)],
        write_paths=[str(repo)],
    )

    with pytest.raises(SandboxViolationError, match="mount.overlap"):
        backend.build_plan(spec)


def test_container_backend_filters_environment_to_allowlist_and_records_resource_limits(tmp_path):
    repo = tmp_path / "repo"
    src = repo / "src"
    out = repo / "out"
    src.mkdir(parents=True)
    out.mkdir()
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["python", "-m", "pytest"],
        cwd=str(repo),
        env={"ALLOWED": "yes", "SECRET": "no"},
        env_allowlist=["ALLOWED"],
        read_paths=[str(src)],
        write_paths=[str(out)],
        resource_limits=SandboxResourceLimits(cpu_count=1, memory_mb=256, process_limit=32),
    )

    plan = backend.build_plan(spec)

    assert plan.env == {"ALLOWED": "yes"}
    assert plan.network_access is False
    assert plan.resource_limits.cpu_count == 1
    assert plan.resource_limits.memory_mb == 256
    assert plan.resource_limits.process_limit == 32
    assert plan.read_mounts == [Path(src).resolve()]
    assert plan.write_mounts == [Path(out).resolve()]


def test_container_backend_enforces_stdout_and_stderr_limits(tmp_path):
    repo = tmp_path / "repo"
    src = repo / "src"
    out = repo / "out"
    src.mkdir(parents=True)
    out.mkdir()
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["python", "-c", "print('x' * 100)"],
        cwd=str(repo),
        read_paths=[str(src)],
        write_paths=[str(out)],
        stdout_limit_bytes=24,
        stderr_limit_bytes=24,
    )

    result = backend.execute(spec)

    assert result.exit_code == 0
    assert len(result.stdout.encode("utf-8")) <= 24
    assert len(result.stderr.encode("utf-8")) <= 24
