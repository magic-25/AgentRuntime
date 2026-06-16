from agent_runtime_contrib.conformance import ConformanceRunner
from agent_runtime_contrib.packs.adapters.openai import OpenAIAdapterPack
from agent_runtime_contrib.packs.base import PackMetadata


def test_conformance_runner_passes_translate_only_adapter_pack():
    report = ConformanceRunner().run_adapter_pack(OpenAIAdapterPack())

    assert report.passed is True
    assert report.pack_id == "openai"
    assert "metadata_valid" in report.checks
    assert "translate_only" in report.checks
    assert report.failure_reasons == []


def test_conformance_runner_rejects_adapter_metadata_declaring_capabilities():
    metadata = PackMetadata(
        pack_id="unsafe-adapter",
        kind="adapter",
        support_level="preview",
        dependencies_group="unsafe-adapter",
        capabilities_declared=["tool.invoke:*"],
    )

    report = ConformanceRunner().run_metadata(metadata)

    assert report.passed is False
    assert "adapter_capability_declared" in report.failure_reasons
