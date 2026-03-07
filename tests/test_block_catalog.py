from __future__ import annotations

import textwrap

import pytest

from stackwarden.domain.block_catalog import default_layer_catalog, load_layer_catalog


def test_default_layer_catalog_has_large_seed_set(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    catalog = default_layer_catalog()
    assert len(catalog.presets) >= 20
    assert len(catalog.presets) < 40
    assert any(c.id == "llm_serving" for c in catalog.categories)
    assert any(c.id == "diffusion" for c in catalog.categories)
    assert any(c.id == "vision_inference" for c in catalog.categories)
    assert any(c.id == "speech_audio" for c in catalog.categories)
    assert any(c.id == "agentic_workflows" for c in catalog.categories)
    assert any(c.id == "inference_optimization" for c in catalog.categories)
    assert any(c.id == "robotics_edge" for c in catalog.categories)
    assert any(p.id == "vllm_model_runtime" for p in catalog.presets)
    assert any(p.id == "flux_schnell_runtime" for p in catalog.presets)
    assert any(p.id == "whisper_asr" for p in catalog.presets)
    assert any(p.id == "agent_orchestration" for p in catalog.presets)
    assert any(p.id == "sdpa_attention_optimization" for p in catalog.presets)
    assert any(p.id == "ubuntu_24_04_runtime" for p in catalog.presets)


def test_load_layer_catalog_uses_defaults_when_override_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    loaded = load_layer_catalog()
    assert len(loaded.presets) >= 20
    ids = {p.id for p in loaded.presets}
    assert "vllm_model_runtime" in ids
    assert "fastapi" in ids
    assert "flux_schnell_runtime" in ids
    assert "agent_orchestration" in ids


def test_load_layer_catalog_rejects_duplicate_ids(tmp_path):
    target = tmp_path / "block_catalog.yaml"
    target.write_text(
        textwrap.dedent(
            """
            schema_version: 1
            revision: 1
            categories:
              - id: test
                label: Test
            presets:
              - id: duplicate
                display_name: One
                category: test
                block_kind: runtime
              - id: duplicate
                display_name: Two
                category: test
                block_kind: runtime
            """
        ).strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_layer_catalog(path=target)
