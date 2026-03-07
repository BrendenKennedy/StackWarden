"""Layer preset catalog schema and persistence helpers."""

from __future__ import annotations

from pathlib import Path
import re

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from stackwarden.config import block_catalog_path


class LayerPresetPipDep(BaseModel):
    name: str
    version: str = ""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("pip dependency name must not be empty")
        return value


class LayerPreset(BaseModel):
    id: str
    display_name: str
    description: str = ""
    category: str
    tags: list[str] = Field(default_factory=list)
    pip: list[LayerPresetPipDep] = Field(default_factory=list)
    apt: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)
    entrypoint_cmd: list[str] = Field(default_factory=list)
    requires: dict[str, object] = Field(default_factory=dict)
    provides: dict[str, object] = Field(default_factory=dict)
    layers: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        value = v.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_\-]{2,63}", value):
            raise ValueError("invalid preset id format")
        return value

    @field_validator("display_name", "category")
    @classmethod
    def _validate_required_text(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("apt", mode="before")
    @classmethod
    def _normalize_apt(cls, v: list[str] | None) -> list[str]:
        items = [str(x).strip() for x in (v or []) if str(x).strip()]
        return items

    @field_validator("ports")
    @classmethod
    def _validate_ports(cls, v: list[int]) -> list[int]:
        for port in v:
            if port < 1 or port > 65535:
                raise ValueError("port must be 1..65535")
        return v

    @field_validator("env")
    @classmethod
    def _validate_env(cls, v: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, value in v.items():
            k = str(key).strip()
            if not k:
                raise ValueError("env key must not be empty")
            cleaned[k] = str(value)
        return cleaned


class LayerPresetCategory(BaseModel):
    id: str
    label: str
    description: str = ""

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        value = v.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_\-]{1,63}", value):
            raise ValueError("invalid category id")
        return value

    @field_validator("label")
    @classmethod
    def _validate_label(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("category label must not be empty")
        return value


class LayerPresetCatalog(BaseModel):
    schema_version: int = 1
    revision: int = 1
    categories: list[LayerPresetCategory] = Field(default_factory=list)
    presets: list[LayerPreset] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_uniqueness(self) -> "LayerPresetCatalog":
        ids = [p.id for p in self.presets]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate preset ids in layer catalog")
        cat_ids = [c.id for c in self.categories]
        if len(cat_ids) != len(set(cat_ids)):
            raise ValueError("duplicate category ids in layer catalog")
        known_categories = set(cat_ids)
        for preset in self.presets:
            if preset.category not in known_categories:
                raise ValueError(f"unknown category for preset '{preset.id}': {preset.category}")
        return self


_CATEGORY_ROWS: list[tuple[str, str, str]] = [
    ("llm_serving", "LLM Serving", "LLM serving runtimes and API servers."),
    ("diffusion", "Diffusion and Image Generation", "Diffusion runtimes, APIs, and image generation utilities."),
    ("vision_inference", "Vision Inference", "Vision model serving, preprocessing, and inference utilities."),
    ("speech_audio", "Speech and Audio", "ASR, TTS, diarization, and streaming audio inference tools."),
    ("data_rag", "Data and RAG", "Embeddings, vector DB clients, and ingestion utilities."),
    ("agentic_workflows", "Agentic Workflows", "Agent orchestration, tool routing, and memory/runtime components."),
    ("inference_optimization", "Inference Optimization", "Export, quantization, and acceleration helpers for production inference."),
    ("api_app", "Serving APIs and Workers", "Serving API frameworks, gateways, and worker orchestration utilities."),
    ("observability", "Observability and Evaluation", "Metrics, tracing, profiling, and inference quality observability tools."),
    ("infra", "Inference Infra and Data Services", "Runtime, security, storage, cache, and infrastructure helpers for inference apps."),
    ("robotics_edge", "Robotics and Edge (Pilot)", "Pilot presets for robotics and edge-device inference workflows."),
    ("training", "Training and Fine-Tuning (Advanced)", "Advanced training/fine-tuning utilities maintained separately from inference-first defaults."),
]

_BASE_PRESETS: list[dict[str, object]] = [
    {"id": "ubuntu_24_04_runtime", "display_name": "Ubuntu 24.04 Runtime", "category": "infra", "block_kind": "runtime", "tags": ["system", "runtime", "ubuntu"], "apt": ["ca-certificates", "curl", "tzdata"], "layers": ["system_runtime_layer"]},
    {"id": "debian_system_runtime", "display_name": "Debian System Runtime", "category": "infra", "block_kind": "runtime", "tags": ["system", "runtime", "debian"], "apt": ["ca-certificates", "wget", "tzdata"], "layers": ["system_runtime_layer"]},
    {"id": "cudnn", "display_name": "cuDNN Runtime", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["cuda", "cudnn"], "apt": ["libcudnn9"], "layers": ["driver_accelerator_layer"]},
    {"id": "nccl_accelerator", "display_name": "NCCL Accelerator", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["cuda", "nccl"], "pip": [("nvidia-nccl-cu12", ">=2.23,<3.0")], "layers": ["driver_accelerator_layer"]},
    {"id": "pytorch_core_compute", "display_name": "PyTorch Core Compute", "category": "inference_optimization", "block_kind": "runtime", "tags": ["torch", "core", "compute"], "pip": [("torch", ">=2.4,<2.8")], "layers": ["core_compute_layer"]},
    {"id": "onnx_core_compute", "display_name": "ONNX Core Compute", "category": "inference_optimization", "block_kind": "runtime", "tags": ["onnx", "core", "compute"], "pip": [("onnxruntime-gpu", ">=1.19,<1.21")], "layers": ["core_compute_layer"]},
    {"id": "vllm_model_runtime", "display_name": "vLLM Model Runtime", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "runtime"], "pip": [("vllm", ">=0.8.3,<1.0")], "layers": ["inference_engine_layer"]},
    {"id": "sglang_model_runtime", "display_name": "SGLang Model Runtime", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "runtime"], "pip": [("sglang", ">=0.4,<0.7")], "layers": ["inference_engine_layer"]},
    {"id": "flux_schnell_runtime", "display_name": "Flux Schnell Runtime", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "flux"], "pip": [("diffusers", ">=0.32,<0.35"), ("transformers", ">=4.55,<4.60"), ("accelerate", ">=0.26,<1.0"), ("safetensors", ">=0.4,<1.0"), ("huggingface-hub", ">=0.26,<1.0")], "layers": ["inference_engine_layer"]},
    {"id": "syncdreamer_runtime", "display_name": "SyncDreamer Runtime", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "syncdreamer"], "pip": [("diffusers", ">=0.32,<0.35"), ("transformers", ">=4.55,<4.60"), ("accelerate", ">=0.26,<1.0"), ("safetensors", ">=0.4,<1.0"), ("huggingface-hub", ">=0.26,<1.0")], "layers": ["inference_engine_layer"]},
    {"id": "hunyuan3d2_runtime", "display_name": "Hunyuan3D-2 Runtime", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "hunyuan", "3d"], "pip": [("diffusers", ">=0.32,<0.35"), ("transformers", ">=4.55,<4.60"), ("accelerate", ">=0.26,<1.0"), ("safetensors", ">=0.4,<1.0"), ("huggingface-hub", ">=0.26,<1.0")], "layers": ["inference_engine_layer"]},
    {"id": "whisper_asr", "display_name": "Whisper ASR Runtime", "category": "speech_audio", "block_kind": "runtime", "tags": ["asr", "speech"], "pip": [("faster-whisper", ">=1.1,<2.0"), ("soundfile", ">=0.12,<1.0")], "layers": ["inference_engine_layer"]},
    {"id": "sentence_transformers_embedding", "display_name": "Sentence Transformers Embeddings", "category": "data_rag", "block_kind": "runtime", "tags": ["embeddings", "rag"], "pip": [("sentence-transformers", ">=3.0,<4.0")], "layers": ["inference_engine_layer"]},
    {"id": "sdpa_attention_optimization", "display_name": "SDPA Attention Optimization", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["optimization", "attention", "sdpa"], "layers": ["optimization_compilation_layer"]},
    {"id": "torch_compile_optimization", "display_name": "torch.compile Optimization", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["optimization", "compile", "pytorch"], "layers": ["optimization_compilation_layer"]},
    {"id": "flash_attention", "display_name": "Flash Attention (Explicit)", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["optimization", "attention", "cuda"], "pip": [("flash-attn", ">=2.6,<3.0")], "layers": ["optimization_compilation_layer"], "requires": {"arch": "amd64", "gpu_vendor": "nvidia", "container_runtime": "nvidia", "cuda_runtime": {"min": 12.0}}},
    {"id": "fastapi", "display_name": "FastAPI API Layer", "category": "api_app", "block_kind": "api", "tags": ["api", "python"], "pip": [("fastapi", "==0.115.*"), ("uvicorn", "[standard]==0.30.*")], "layers": ["serving_layer"]},
    {"id": "grpc_serving", "display_name": "gRPC Serving Layer", "category": "api_app", "block_kind": "api", "tags": ["grpc", "api"], "pip": [("grpcio", ">=1.66,<2.0"), ("grpcio-tools", ">=1.66,<2.0"), ("protobuf", ">=5.28,<6.0")], "layers": ["serving_layer"]},
    {"id": "agent_orchestration", "display_name": "Agent Orchestration", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["agent", "orchestration"], "pip": [("langchain", ">=0.3,<0.4"), ("pydantic", ">=2.8,<3.0")], "layers": ["application_orchestration_layer"]},
    {"id": "celery_orchestration", "display_name": "Celery Orchestration", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["worker", "orchestration"], "pip": [("celery", ">=5.4,<6.0"), ("redis", ">=5.0,<6.0")], "layers": ["application_orchestration_layer"]},
    {"id": "prometheus_observability", "display_name": "Prometheus Observability", "category": "observability", "block_kind": "runtime", "tags": ["observability", "metrics"], "pip": [("prometheus-client", ">=0.21,<1.0")], "layers": ["observability_operations_layer"]},
    {"id": "otel_observability", "display_name": "OpenTelemetry Observability", "category": "observability", "block_kind": "runtime", "tags": ["observability", "tracing"], "pip": [("opentelemetry-api", ">=1.28,<2.0"), ("opentelemetry-sdk", ">=1.28,<2.0")], "layers": ["observability_operations_layer"]},
]

def _to_pip(items: list[tuple[str, str]]) -> list[LayerPresetPipDep]:
    return [LayerPresetPipDep(name=name, version=version) for name, version in items]


def _base_preset_to_model(row: dict[str, object]) -> LayerPreset:
    base_id = str(row["id"])
    manual = bool(row.get("manual", False))
    ports = [8000] if str(row["block_kind"]) == "api" else []
    requires: dict[str, object] = {} if manual else {"os": "linux"}
    requires.update(dict(row.get("requires", {})))
    block_kind = str(row.get("block_kind", "runtime"))
    category = str(row.get("category", ""))
    layers: list[str] = list(row.get("layers", []))
    if not layers:
        if block_kind == "accelerator":
            layers = ["driver_accelerator_layer", "optimization_compilation_layer"]
        elif block_kind == "api":
            layers = ["serving_layer", "application_orchestration_layer"]
        else:
            layers = ["inference_engine_layer"]
        if category in {"infra"}:
            layers.append("system_runtime_layer")
        if category in {"robotics_edge"}:
            layers = ["application_orchestration_layer", "inference_engine_layer"]
        if category in {"observability"}:
            layers = ["observability_operations_layer"]
    provides = {
        "preset_group": base_id,
    }
    return LayerPreset(
        id=base_id,
        display_name=str(row["display_name"]),
        description=f"Opinionated preset for {row['display_name']}.",
        category=str(row["category"]),
        tags=list(row.get("tags", [])) if manual else [*list(row.get("tags", [])), "preset"],
        pip=_to_pip(list(row.get("pip", []))),
        apt=list(row.get("apt", [])),
        env={} if manual else {"STACKWARDEN_PROFILE": "balanced"},
        ports=[] if manual else ports,
        entrypoint_cmd=[] if manual else (["python", "-m", "uvicorn"] if str(row["block_kind"]) == "api" else []),
        requires=requires,
        provides=provides,
        layers=layers,
    )


def default_layer_catalog() -> LayerPresetCatalog:
    categories = [
        LayerPresetCategory(id=cid, label=label, description=description)
        for cid, label, description in _CATEGORY_ROWS
    ]
    presets = [_base_preset_to_model(row) for row in _BASE_PRESETS]
    return LayerPresetCatalog(
        schema_version=1,
        revision=1,
        categories=categories,
        presets=presets,
    )


def load_layer_catalog(path: Path | None = None) -> LayerPresetCatalog:
    target = path or block_catalog_path()
    base = default_layer_catalog()
    if not target.exists():
        return base
    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    # Overlay file values while keeping robust defaults.
    merged = {
        "schema_version": raw.get("schema_version", base.schema_version),
        "revision": raw.get("revision", base.revision),
        "categories": raw.get("categories", [c.model_dump(mode="json") for c in base.categories]),
        "presets": raw.get("presets", [p.model_dump(mode="json") for p in base.presets]),
    }
    return LayerPresetCatalog.model_validate(merged)

