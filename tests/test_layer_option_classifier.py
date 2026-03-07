from __future__ import annotations

import types

from stackwarden.application.layer_option_classifier import classify_layer_options


def _layer(
    id_: str,
    stack_layer: str,
    tags: list[str],
    *,
    incompatible_with: list[str] | None = None,
    requires: dict[str, object] | None = None,
):
    return types.SimpleNamespace(
        id=id_,
        display_name=id_.replace("_", " ").title(),
        stack_layer=stack_layer,
        tags=tags,
        incompatible_with=incompatible_with or [],
        requires=requires or {},
    )


def test_classify_layer_options_marks_recommended_by_intent(monkeypatch):
    layers = {
        "vllm_runtime": _layer("vllm_runtime", "inference_engine_layer", ["llm", "serving"]),
        "onnx_runtime": _layer("onnx_runtime", "inference_engine_layer", ["vision"]),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="llm", inference_profile="balanced")
    grouped = {group.stack_layer: group.options for group in groups}
    inference_opts = grouped["inference_engine_layer"]
    first = inference_opts[0]
    assert first.id == "vllm_runtime"
    assert first.tier == "recommended"


def test_classify_layer_options_vision_blocks_flux(monkeypatch):
    layers = {
        "flux_runtime": _layer("flux_runtime", "inference_engine_layer", ["diffusion", "flux"]),
        "vision_onnx": _layer("vision_onnx", "inference_engine_layer", ["vision", "onnx"]),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="vision")
    grouped = {group.stack_layer: group.options for group in groups}
    opts = {item.id: item for item in grouped["inference_engine_layer"]}
    assert opts["flux_runtime"].tier == "incompatible"
    assert opts["vision_onnx"].tier == "recommended"


def test_classify_layer_options_marks_incompatible_against_selected(monkeypatch):
    layers = {
        "runtime_cpu": _layer("runtime_cpu", "system_runtime_layer", ["runtime"]),
        "cuda_runtime": _layer(
            "cuda_runtime",
            "driver_accelerator_layer",
            ["cuda", "accelerator"],
            incompatible_with=["runtime_cpu"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(
        selected_layers=["runtime_cpu"],
        inference_type="diffusion",
        inference_profile="latency",
    )
    grouped = {group.stack_layer: group.options for group in groups}
    cuda = next(item for item in grouped["driver_accelerator_layer"] if item.id == "cuda_runtime")
    assert cuda.tier == "incompatible"
    assert any("runtime_cpu" in reason for reason in cuda.reasons)


def test_classify_layer_options_orders_groups_high_to_low(monkeypatch):
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: [],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="vision")
    assert [group.stack_layer for group in groups] == [
        "inference_engine_layer",
        "optimization_compilation_layer",
        "core_compute_layer",
        "driver_accelerator_layer",
        "system_runtime_layer",
        "application_orchestration_layer",
        "observability_operations_layer",
        "serving_layer",
    ]


def test_classify_layer_options_vision_surfaces_multiple_compatible_runtimes(monkeypatch):
    layers = {
        "vision_onnx_runtime": _layer(
            "vision_onnx_runtime",
            "inference_engine_layer",
            ["vision", "onnx", "classification"],
        ),
        "ultralytics_vision_runtime": _layer(
            "ultralytics_vision_runtime",
            "inference_engine_layer",
            ["vision", "detector", "segmentation"],
        ),
        "torchvision_vision_runtime": _layer(
            "torchvision_vision_runtime",
            "inference_engine_layer",
            ["vision", "classification"],
        ),
        "flux_runtime": _layer("flux_runtime", "inference_engine_layer", ["diffusion", "flux"]),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="vision")
    grouped = {group.stack_layer: group.options for group in groups}
    vision_options = grouped["inference_engine_layer"]
    compatible_ids = [item.id for item in vision_options if item.tier in {"recommended", "compatible"}]

    assert len(compatible_ids) >= 3
    assert "vision_onnx_runtime" in compatible_ids
    assert "ultralytics_vision_runtime" in compatible_ids
    assert "torchvision_vision_runtime" in compatible_ids


def test_classify_layer_options_normalizes_arm_and_os_aliases_for_flux(monkeypatch):
    layers = {
        "flux_schnell_runtime": _layer(
            "flux_schnell_runtime",
            "inference_engine_layer",
            ["diffusion", "flux", "image-gen"],
            requires={
                "arch": "aarch64",
                "os_version_id": "ubuntu_24_04",
                "gpu_vendor": "nvidia",
            },
        ),
    }
    profile = types.SimpleNamespace(
        arch=types.SimpleNamespace(value="arm64"),
        os="linux",
        os_family="ubuntu",
        os_version="24.04",
        os_family_id=None,
        os_version_id=None,
        container_runtime=types.SimpleNamespace(value="nvidia"),
        gpu=types.SimpleNamespace(vendor="nvidia", vendor_id=None, family="blackwell", family_id=None),
        host_facts=types.SimpleNamespace(confidence={}),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_profile",
        lambda _profile_id: profile,
    )

    groups = classify_layer_options(
        selected_layers=[],
        inference_type="diffusion",
        target_profile_id="dgx-spark-arm",
    )
    grouped = {group.stack_layer: group.options for group in groups}
    flux = next(item for item in grouped["inference_engine_layer"] if item.id == "flux_schnell_runtime")

    assert flux.tier == "recommended"


def test_classify_layer_options_recommends_optimization_layers_for_multiple_intents(monkeypatch):
    layers = {
        "sdpa_attention_optimization": _layer(
            "sdpa_attention_optimization",
            "optimization_compilation_layer",
            ["optimization", "attention", "sdpa"],
        ),
        "torch_compile_optimization": _layer(
            "torch_compile_optimization",
            "optimization_compilation_layer",
            ["optimization", "compile", "pytorch"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    for inference_type in ["vision", "asr", "embeddings", "rag", "general"]:
        groups = classify_layer_options(selected_layers=[], inference_type=inference_type)
        grouped = {group.stack_layer: group.options for group in groups}
        opt_tiers = {item.id: item.tier for item in grouped["optimization_compilation_layer"]}
        assert any(tier == "recommended" for tier in opt_tiers.values())


def test_classify_layer_options_recommends_unsloth_for_llm_finetune(monkeypatch):
    layers = {
        "unsloth_finetune_optimization": _layer(
            "unsloth_finetune_optimization",
            "optimization_compilation_layer",
            ["optimization", "llm", "finetune", "lora", "qlora", "unsloth"],
        ),
        "sdpa_attention_optimization": _layer(
            "sdpa_attention_optimization",
            "optimization_compilation_layer",
            ["optimization", "attention", "sdpa"],
        ),
        "vllm_model_runtime": _layer(
            "vllm_model_runtime",
            "inference_engine_layer",
            ["runtime", "llm", "inference", "vllm"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="llm_finetune")
    grouped = {group.stack_layer: group.options for group in groups}
    opts = {item.id: item for item in grouped["optimization_compilation_layer"]}
    assert opts["unsloth_finetune_optimization"].tier == "recommended"


def test_classify_layer_options_serving_prefers_tensorrt_and_blocks_unsloth(monkeypatch):
    layers = {
        "unsloth_finetune_optimization": _layer(
            "unsloth_finetune_optimization",
            "optimization_compilation_layer",
            ["optimization", "llm", "finetune", "unsloth", "qlora"],
        ),
        "tensorrt_llm_serving_optimization": _layer(
            "tensorrt_llm_serving_optimization",
            "optimization_compilation_layer",
            ["optimization", "serving", "llm", "tensorrt", "nvidia"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="llm_serving")
    grouped = {group.stack_layer: group.options for group in groups}
    opts = {item.id: item for item in grouped["optimization_compilation_layer"]}
    assert opts["tensorrt_llm_serving_optimization"].tier == "recommended"
    assert opts["unsloth_finetune_optimization"].tier == "incompatible"


def test_classify_layer_options_diffusion_recommends_core_compute_and_accelerator(monkeypatch):
    layers = {
        "pytorch_core_compute": _layer(
            "pytorch_core_compute",
            "core_compute_layer",
            ["torch", "pytorch", "compute", "core"],
        ),
        "nccl_accelerator": _layer(
            "nccl_accelerator",
            "driver_accelerator_layer",
            ["cuda", "accelerator", "nccl"],
        ),
        "flux_schnell_runtime": _layer(
            "flux_schnell_runtime",
            "inference_engine_layer",
            ["diffusion", "flux", "image-gen"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    groups = classify_layer_options(selected_layers=[], inference_type="diffusion")
    grouped = {group.stack_layer: group.options for group in groups}
    core_opts = {item.id: item for item in grouped["core_compute_layer"]}
    accel_opts = {item.id: item for item in grouped["driver_accelerator_layer"]}

    assert core_opts["pytorch_core_compute"].tier == "recommended"
    assert accel_opts["nccl_accelerator"].tier == "recommended"


def test_classify_layer_options_recommends_foundational_layers_across_inference_families(monkeypatch):
    layers = {
        "pytorch_core_compute": _layer(
            "pytorch_core_compute",
            "core_compute_layer",
            ["torch", "pytorch", "compute", "core"],
        ),
        "nccl_accelerator": _layer(
            "nccl_accelerator",
            "driver_accelerator_layer",
            ["cuda", "accelerator", "nccl"],
        ),
        "vllm_runtime": _layer(
            "vllm_runtime",
            "inference_engine_layer",
            ["llm", "vllm", "runtime"],
        ),
        "whisper_asr_runtime": _layer(
            "whisper_asr_runtime",
            "inference_engine_layer",
            ["asr", "whisper", "speech"],
        ),
        "vision_onnx_runtime": _layer(
            "vision_onnx_runtime",
            "inference_engine_layer",
            ["vision", "onnx", "classification"],
        ),
        "flux_runtime": _layer(
            "flux_runtime",
            "inference_engine_layer",
            ["diffusion", "flux", "image-gen"],
        ),
    }
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.list_layer_ids",
        lambda: list(layers.keys()),
    )
    monkeypatch.setattr(
        "stackwarden.application.layer_option_classifier.load_layer",
        lambda layer_id: layers[layer_id],
    )

    for inference_type in ["llm", "diffusion", "asr", "vision", "embeddings", "tts"]:
        groups = classify_layer_options(selected_layers=[], inference_type=inference_type)
        grouped = {group.stack_layer: group.options for group in groups}
        core_opts = {item.id: item for item in grouped["core_compute_layer"]}
        accel_opts = {item.id: item for item in grouped["driver_accelerator_layer"]}
        assert core_opts["pytorch_core_compute"].tier == "recommended"
        assert accel_opts["nccl_accelerator"].tier == "recommended"
