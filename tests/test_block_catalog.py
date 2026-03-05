from __future__ import annotations

import textwrap

import pytest

from stackwarden.domain.block_catalog import default_block_catalog, load_block_catalog


def test_default_block_catalog_has_large_seed_set(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    catalog = default_block_catalog()
    assert len(catalog.presets) >= 80
    assert len(catalog.presets) < 150
    assert any(c.id == "llm_serving" for c in catalog.categories)
    assert any(c.id == "diffusion" for c in catalog.categories)
    assert any(c.id == "vision_inference" for c in catalog.categories)
    assert any(c.id == "speech_audio" for c in catalog.categories)
    assert any(c.id == "agentic_workflows" for c in catalog.categories)
    assert any(c.id == "inference_optimization" for c in catalog.categories)
    assert any(c.id == "robotics_edge" for c in catalog.categories)
    assert any(p.id == "diffusers_runtime" for p in catalog.presets)
    assert any(p.id == "ultralytics_yolo" for p in catalog.presets)
    assert any(p.id == "faster_whisper_asr" for p in catalog.presets)
    assert any(p.id == "langgraph_runtime" for p in catalog.presets)
    assert any(p.id == "onnx_export_tools" for p in catalog.presets)
    assert any(p.id == "ros2_runtime" for p in catalog.presets)


def test_load_block_catalog_uses_defaults_when_override_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STACKWARDEN_DATA_DIR", str(tmp_path))
    loaded = load_block_catalog()
    assert len(loaded.presets) >= 80
    ids = {p.id for p in loaded.presets}
    assert "vllm" in ids
    assert "fastapi_api" in ids
    assert "diffusers_runtime" in ids
    assert "langgraph_runtime" in ids


def test_load_block_catalog_rejects_duplicate_ids(tmp_path):
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
        load_block_catalog(path=target)
