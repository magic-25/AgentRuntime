from pathlib import Path

import pytest

from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxViolationError
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend


def test_container_backend_rejects_path_traversal_outside_cwd(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["python", "-V"],
        cwd=str(repo),
        read_paths=[str(repo / "..")],
        write_paths=[],
    )

    with pytest.raises(SandboxViolationError, match="path.escape"):
        backend.build_plan(spec)


def test_container_backend_rejects_symlink_escape_outside_cwd(tmp_path):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    repo.mkdir()
    link = repo / "linked-outside"
    link.symlink_to(outside, target_is_directory=True)
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["python", "-V"],
        cwd=str(repo),
        read_paths=[str(link)],
        write_paths=[],
    )

    with pytest.raises(SandboxViolationError, match="path.escape"):
        backend.build_plan(spec)


def test_container_backend_rejects_host_credentials_and_docker_socket(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    backend = ContainerSandboxBackend()
    denied_paths = [
        Path.home() / ".ssh" / "id_rsa",
        Path("/var/run/docker.sock"),
        Path.home() / ".git-credentials",
    ]

    for denied_path in denied_paths:
        spec = SandboxCommandSpec(
            argv=["python", "-V"],
            cwd=str(repo),
            read_paths=[str(denied_path)],
            write_paths=[],
        )
        with pytest.raises(SandboxViolationError, match="credential.denied"):
            backend.build_plan(spec)


def test_container_backend_denies_network_attempt_by_default(tmp_path):
    repo = tmp_path / "repo"
    src = repo / "src"
    out = repo / "out"
    src.mkdir(parents=True)
    out.mkdir()
    backend = ContainerSandboxBackend()
    spec = SandboxCommandSpec(
        argv=["curl", "https://example.com"],
        cwd=str(repo),
        read_paths=[str(src)],
        write_paths=[str(out)],
        network_access=True,
    )

    with pytest.raises(SandboxViolationError, match="sandbox.network_denied"):
        backend.execute(spec)
