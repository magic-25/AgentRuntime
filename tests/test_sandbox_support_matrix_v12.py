from agent_runtime.release import production_release_manifest
from agent_runtime_contrib.packs.base import PackMetadata
from agent_runtime_contrib.packs.sandbox.remote import RemoteSandboxBackend


def test_pack_metadata_allows_remote_contract_beta_without_default_enablement():
    metadata = RemoteSandboxBackend().metadata

    assert isinstance(metadata, PackMetadata)
    assert metadata.support_level == "contract_beta"
    assert metadata.default_enabled is False


def test_release_manifest_includes_1_2_sandbox_support_matrix_without_promoting_remote():
    manifest = production_release_manifest()

    sandbox = manifest["sandbox_runtime_hardening"]

    assert sandbox["version"] == "1.2.0"
    assert sandbox["support_matrix"]["container"]["support_level"] == "stable_candidate"
    assert sandbox["support_matrix"]["sidecar"]["support_level"] == "preview"
    assert sandbox["support_matrix"]["remote"]["support_level"] == "contract_beta"
    assert "remote_executor_backend" not in manifest["supported"]
    assert "absolute_escape_prevention" in sandbox["limitations"]
