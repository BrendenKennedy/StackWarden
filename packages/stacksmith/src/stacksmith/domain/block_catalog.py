"""Block preset catalog schema and persistence helpers."""

from __future__ import annotations

from pathlib import Path
import re

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from stacksmith.config import block_catalog_path


class BlockPresetPipDep(BaseModel):
    name: str
    version: str = ""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("pip dependency name must not be empty")
        return value


class BlockPreset(BaseModel):
    id: str
    display_name: str
    description: str = ""
    category: str
    tags: list[str] = Field(default_factory=list)
    pip: list[BlockPresetPipDep] = Field(default_factory=list)
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


class BlockPresetCategory(BaseModel):
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


class BlockPresetCatalog(BaseModel):
    schema_version: int = 1
    revision: int = 1
    categories: list[BlockPresetCategory] = Field(default_factory=list)
    presets: list[BlockPreset] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_uniqueness(self) -> "BlockPresetCatalog":
        ids = [p.id for p in self.presets]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate preset ids in block catalog")
        cat_ids = [c.id for c in self.categories]
        if len(cat_ids) != len(set(cat_ids)):
            raise ValueError("duplicate category ids in block catalog")
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
    {"id": "vllm", "display_name": "vLLM Runtime", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "inference"], "pip": [("vllm", ">=0.6,<0.8")]},
    {"id": "tgi", "display_name": "Text Generation Inference", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "inference"], "pip": [("text-generation", ">=0.7,<0.9")]},
    {"id": "sglang", "display_name": "SGLang Runtime", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "serving"], "pip": [("sglang", ">=0.3,<0.5")]},
    {"id": "triton_client", "display_name": "Triton Client", "category": "llm_serving", "block_kind": "runtime", "tags": ["triton", "inference"], "pip": [("tritonclient[http]", ">=2.49,<2.53")]},
    {"id": "ray_serve", "display_name": "Ray Serve", "category": "llm_serving", "block_kind": "runtime", "tags": ["ray", "serving"], "pip": [("ray[serve]", ">=2.34,<2.40")]},
    {"id": "litellm", "display_name": "LiteLLM Gateway", "category": "llm_serving", "block_kind": "api", "tags": ["gateway", "llm"], "pip": [("litellm", ">=1.45,<1.60")]},
    {"id": "openai_compat", "display_name": "OpenAI Compat API", "category": "llm_serving", "block_kind": "api", "tags": ["api", "compat"], "pip": [("fastapi", "==0.115.*"), ("uvicorn", "[standard]==0.30.*")]},
    {"id": "outlines", "display_name": "Outlines Structured Decoding", "category": "llm_serving", "block_kind": "runtime", "tags": ["decoding", "llm"], "pip": [("outlines", ">=0.0.46,<0.1")]},
    {"id": "guidance", "display_name": "Guidance Runtime", "category": "llm_serving", "block_kind": "runtime", "tags": ["prompting", "llm"], "pip": [("guidance", ">=0.1,<0.2")]},
    {"id": "llama_cpp", "display_name": "llama.cpp Python", "category": "llm_serving", "block_kind": "runtime", "tags": ["llm", "cpu"], "pip": [("llama-cpp-python", ">=0.2.90,<0.3")]},
    {"id": "diffusers_runtime", "display_name": "Diffusers Runtime", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "image-gen"], "pip": [("diffusers", ">=0.30,<0.34"), ("transformers", ">=4.44,<4.49")]},
    {"id": "comfyui_runtime", "display_name": "ComfyUI Runtime", "category": "diffusion", "block_kind": "api", "tags": ["diffusion", "ui"], "pip": [("comfyui", ">=0.2,<0.3")]},
    {"id": "invokeai_runtime", "display_name": "InvokeAI Runtime", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "serving"], "pip": [("invokeai", ">=5.4,<5.6")]},
    {"id": "controlnet_tools", "display_name": "ControlNet Tooling", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "controlnet"], "pip": [("controlnet-aux", ">=0.0.9,<0.1")]},
    {"id": "safetensors_tools", "display_name": "Safetensors Utilities", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "model-format"], "pip": [("safetensors", ">=0.4.5,<0.5")]},
    {"id": "k_diffusion_tools", "display_name": "K-Diffusion Helpers", "category": "diffusion", "block_kind": "runtime", "tags": ["diffusion", "sampling"], "pip": [("k-diffusion", ">=0.1.1,<0.2")]},
    {"id": "onnxruntime_vision", "display_name": "ONNX Runtime Vision", "category": "vision_inference", "block_kind": "runtime", "tags": ["vision", "onnx"], "pip": [("onnxruntime-gpu", ">=1.19,<1.21")]},
    {"id": "ultralytics_yolo", "display_name": "Ultralytics YOLO", "category": "vision_inference", "block_kind": "api", "tags": ["vision", "detection"], "pip": [("ultralytics", ">=8.2,<8.4")]},
    {"id": "opencv_runtime", "display_name": "OpenCV Runtime", "category": "vision_inference", "block_kind": "runtime", "tags": ["vision", "preprocess"], "pip": [("opencv-python-headless", ">=4.10,<4.12")]},
    {"id": "detectron2_runtime", "display_name": "Detectron2 Runtime", "category": "vision_inference", "block_kind": "runtime", "tags": ["vision", "segmentation"], "pip": [("detectron2", ">=0.6,<0.7")]},
    {"id": "timm_inference", "display_name": "timm Inference", "category": "vision_inference", "block_kind": "runtime", "tags": ["vision", "classification"], "pip": [("timm", ">=1.0.9,<1.1")]},
    {"id": "pillow_simd_tools", "display_name": "Pillow SIMD Tools", "category": "vision_inference", "block_kind": "accelerator", "tags": ["vision", "image-io"], "pip": [("pillow-simd", ">=10.4,<10.6")]},
    {"id": "faster_whisper_asr", "display_name": "Faster-Whisper ASR", "category": "speech_audio", "block_kind": "api", "tags": ["asr", "speech"], "pip": [("faster-whisper", ">=1.0,<1.1")]},
    {"id": "whisperx_asr", "display_name": "WhisperX ASR", "category": "speech_audio", "block_kind": "runtime", "tags": ["asr", "alignment"], "pip": [("whisperx", ">=3.2,<3.4")]},
    {"id": "coqui_tts_runtime", "display_name": "Coqui TTS Runtime", "category": "speech_audio", "block_kind": "api", "tags": ["tts", "speech"], "pip": [("TTS", ">=0.22,<0.24")]},
    {"id": "piper_tts_runtime", "display_name": "Piper TTS Runtime", "category": "speech_audio", "block_kind": "runtime", "tags": ["tts", "edge"], "pip": [("piper-tts", ">=1.2,<1.4")]},
    {"id": "pyannote_diarization", "display_name": "PyAnnote Diarization", "category": "speech_audio", "block_kind": "runtime", "tags": ["speech", "diarization"], "pip": [("pyannote.audio", ">=3.3,<3.4")]},
    {"id": "silero_vad", "display_name": "Silero VAD", "category": "speech_audio", "block_kind": "runtime", "tags": ["speech", "vad"], "pip": [("silero-vad", ">=5.1,<5.2")]},
    {"id": "deepspeed", "display_name": "DeepSpeed", "category": "training", "block_kind": "accelerator", "tags": ["training", "distributed"], "pip": [("deepspeed", ">=0.14,<0.16")]},
    {"id": "accelerate", "display_name": "HuggingFace Accelerate", "category": "training", "block_kind": "runtime", "tags": ["training", "hf"], "pip": [("accelerate", ">=0.34,<0.37")]},
    {"id": "trl", "display_name": "TRL", "category": "training", "block_kind": "runtime", "tags": ["rlhf", "training"], "pip": [("trl", ">=0.10,<0.12")]},
    {"id": "peft", "display_name": "PEFT", "category": "training", "block_kind": "runtime", "tags": ["lora", "training"], "pip": [("peft", ">=0.12,<0.14")]},
    {"id": "bitsandbytes", "display_name": "bitsandbytes", "category": "training", "block_kind": "accelerator", "tags": ["quantization", "training"], "pip": [("bitsandbytes", ">=0.43,<0.45")]},
    {
        "id": "flash_attn",
        "display_name": "Flash Attention",
        "category": "training",
        "block_kind": "accelerator",
        "tags": ["cuda", "training"],
        "pip": [("flash-attn", ">=2.6,<2.8")],
        "requires": {
            "arch": "amd64",
            "gpu_vendor": "nvidia",
            "container_runtime": "nvidia",
            "cuda_runtime": {"min": 12.0},
        },
    },
    {"id": "xformers", "display_name": "xFormers", "category": "training", "block_kind": "accelerator", "tags": ["attention", "training"], "pip": [("xformers", ">=0.0.28,<0.0.30")]},
    {"id": "pytorch_lightning", "display_name": "PyTorch Lightning", "category": "training", "block_kind": "runtime", "tags": ["pytorch", "training"], "pip": [("pytorch-lightning", ">=2.4,<2.5")]},
    {"id": "wandb", "display_name": "Weights and Biases", "category": "training", "block_kind": "api", "tags": ["experiment", "tracking"], "pip": [("wandb", ">=0.18,<0.20")]},
    {"id": "mlflow", "display_name": "MLflow", "category": "training", "block_kind": "api", "tags": ["tracking", "registry"], "pip": [("mlflow", ">=2.16,<2.20")]},
    {"id": "sentence_transformers", "display_name": "Sentence Transformers", "category": "data_rag", "block_kind": "runtime", "tags": ["embeddings", "rag"], "pip": [("sentence-transformers", ">=3.1,<3.4")]},
    {"id": "langchain", "display_name": "LangChain", "category": "data_rag", "block_kind": "runtime", "tags": ["rag", "agents"], "pip": [("langchain", ">=0.3,<0.4")]},
    {"id": "llama_index", "display_name": "LlamaIndex", "category": "data_rag", "block_kind": "runtime", "tags": ["rag", "index"], "pip": [("llama-index", ">=0.11,<0.12")]},
    {"id": "faiss", "display_name": "FAISS", "category": "data_rag", "block_kind": "accelerator", "tags": ["vector", "index"], "pip": [("faiss-cpu", ">=1.8,<1.10")]},
    {"id": "qdrant_client", "display_name": "Qdrant Client", "category": "data_rag", "block_kind": "runtime", "tags": ["vector", "qdrant"], "pip": [("qdrant-client", ">=1.11,<1.14")]},
    {"id": "milvus_client", "display_name": "Milvus Client", "category": "data_rag", "block_kind": "runtime", "tags": ["vector", "milvus"], "pip": [("pymilvus", ">=2.4,<2.6")]},
    {"id": "chromadb", "display_name": "ChromaDB", "category": "data_rag", "block_kind": "runtime", "tags": ["vector", "chroma"], "pip": [("chromadb", ">=0.5,<0.6")]},
    {"id": "pgvector", "display_name": "pgvector Helpers", "category": "data_rag", "block_kind": "runtime", "tags": ["postgres", "vector"], "pip": [("pgvector", ">=0.3,<0.4")]},
    {"id": "pydantic_ai", "display_name": "PydanticAI", "category": "data_rag", "block_kind": "runtime", "tags": ["agents", "validation"], "pip": [("pydantic-ai", ">=0.0.10,<0.1")]},
    {"id": "unstructured", "display_name": "Unstructured", "category": "data_rag", "block_kind": "runtime", "tags": ["ingestion", "documents"], "pip": [("unstructured", ">=0.15,<0.17")]},
    {"id": "langgraph_runtime", "display_name": "LangGraph Runtime", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["agent", "workflow"], "pip": [("langgraph", ">=0.2.20,<0.3")]},
    {"id": "autogen_runtime", "display_name": "AutoGen Runtime", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["agent", "multi-agent"], "pip": [("autogen-agentchat", ">=0.3,<0.4")]},
    {"id": "crewai_runtime", "display_name": "CrewAI Runtime", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["agent", "orchestration"], "pip": [("crewai", ">=0.95,<0.110")]},
    {"id": "tool_router", "display_name": "Tool Router", "category": "agentic_workflows", "block_kind": "api", "tags": ["agent", "tools"], "pip": [("fastapi", "==0.115.*"), ("httpx", ">=0.27,<0.28")]},
    {"id": "agent_memory", "display_name": "Agent Memory Store", "category": "agentic_workflows", "block_kind": "runtime", "tags": ["agent", "memory"], "pip": [("mem0ai", ">=0.1.50,<0.2")]},
    {"id": "onnx_export_tools", "display_name": "ONNX Export Tools", "category": "inference_optimization", "block_kind": "runtime", "tags": ["optimization", "onnx"], "pip": [("onnx", ">=1.17,<1.18"), ("onnxsim", ">=0.4.36,<0.5")]},
    {"id": "tensorrt_llm_tools", "display_name": "TensorRT-LLM Tools", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["optimization", "tensorrt"], "pip": [("tensorrt-llm", ">=0.13,<0.16")]},
    {"id": "optimum_runtime", "display_name": "HuggingFace Optimum", "category": "inference_optimization", "block_kind": "runtime", "tags": ["optimization", "hf"], "pip": [("optimum", ">=1.22,<1.24")]},
    {"id": "openvino_runtime", "display_name": "OpenVINO Runtime", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["optimization", "cpu"], "pip": [("openvino", ">=2024.3,<2025.0")]},
    {"id": "awq_quantization", "display_name": "AWQ Quantization", "category": "inference_optimization", "block_kind": "accelerator", "tags": ["quantization", "llm"], "pip": [("autoawq", ">=0.2.7,<0.3")]},
    {"id": "gguf_runtime", "display_name": "GGUF Runtime Tools", "category": "inference_optimization", "block_kind": "runtime", "tags": ["quantization", "gguf"], "pip": [("ctransformers", ">=0.2.27,<0.3")]},
    {"id": "fastapi_api", "display_name": "FastAPI API", "category": "api_app", "block_kind": "api", "tags": ["api", "python"], "pip": [("fastapi", "==0.115.*"), ("uvicorn", "[standard]==0.30.*")]},
    {"id": "flask_api", "display_name": "Flask API", "category": "api_app", "block_kind": "api", "tags": ["api", "python"], "pip": [("flask", ">=3.0,<3.1"), ("gunicorn", ">=22,<23")]},
    {"id": "django_api", "display_name": "Django API", "category": "api_app", "block_kind": "api", "tags": ["api", "django"], "pip": [("django", ">=5.1,<5.2"), ("djangorestframework", ">=3.15,<3.16")]},
    {"id": "celery_worker", "display_name": "Celery Worker", "category": "api_app", "block_kind": "runtime", "tags": ["worker", "queue"], "pip": [("celery", ">=5.4,<5.5")]},
    {"id": "rq_worker", "display_name": "RQ Worker", "category": "api_app", "block_kind": "runtime", "tags": ["worker", "queue"], "pip": [("rq", ">=1.16,<1.17")]},
    {"id": "dramatiq_worker", "display_name": "Dramatiq Worker", "category": "api_app", "block_kind": "runtime", "tags": ["worker", "queue"], "pip": [("dramatiq", ">=1.17,<1.18")]},
    {"id": "grpc_server", "display_name": "gRPC Server", "category": "api_app", "block_kind": "api", "tags": ["grpc", "api"], "pip": [("grpcio", ">=1.66,<1.68"), ("grpcio-tools", ">=1.66,<1.68")]},
    {"id": "streamlit", "display_name": "Streamlit App", "category": "api_app", "block_kind": "api", "tags": ["ui", "streamlit"], "pip": [("streamlit", ">=1.39,<1.42")]},
    {"id": "gradio", "display_name": "Gradio App", "category": "api_app", "block_kind": "api", "tags": ["ui", "gradio"], "pip": [("gradio", ">=5.4,<5.8")]},
    {"id": "dash", "display_name": "Dash App", "category": "api_app", "block_kind": "api", "tags": ["ui", "dash"], "pip": [("dash", ">=2.18,<2.20")]},
    {"id": "prometheus_client", "display_name": "Prometheus Client", "category": "observability", "block_kind": "runtime", "tags": ["metrics", "prometheus"], "pip": [("prometheus-client", ">=0.21,<0.22")]},
    {"id": "opentelemetry", "display_name": "OpenTelemetry", "category": "observability", "block_kind": "runtime", "tags": ["tracing", "otel"], "pip": [("opentelemetry-sdk", ">=1.28,<1.30"), ("opentelemetry-exporter-otlp", ">=1.28,<1.30")]},
    {"id": "structlog", "display_name": "Structured Logging", "category": "observability", "block_kind": "runtime", "tags": ["logging"], "pip": [("structlog", ">=24.4,<25.0")]},
    {"id": "sentry", "display_name": "Sentry SDK", "category": "observability", "block_kind": "runtime", "tags": ["errors", "monitoring"], "pip": [("sentry-sdk", ">=2.17,<2.20")]},
    {"id": "pyroscope", "display_name": "Pyroscope Profiling", "category": "observability", "block_kind": "runtime", "tags": ["profiling"], "pip": [("pyroscope-io", ">=0.8,<0.10")]},
    {"id": "locust", "display_name": "Locust Load Testing", "category": "observability", "block_kind": "runtime", "tags": ["load-testing"], "pip": [("locust", ">=2.31,<2.33")]},
    {"id": "httpx_retries", "display_name": "HTTPX Retries", "category": "observability", "block_kind": "runtime", "tags": ["resilience", "http"], "pip": [("httpx", ">=0.27,<0.28"), ("tenacity", ">=9.0,<9.1")]},
    {"id": "redis_runtime", "display_name": "Redis Runtime", "category": "infra", "block_kind": "runtime", "tags": ["cache", "redis"], "pip": [("redis", ">=5.1,<5.3")]},
    {"id": "postgres_runtime", "display_name": "Postgres Runtime", "category": "infra", "block_kind": "runtime", "tags": ["postgres", "db"], "pip": [("psycopg[binary]", ">=3.2,<3.3")]},
    {"id": "mysql_runtime", "display_name": "MySQL Runtime", "category": "infra", "block_kind": "runtime", "tags": ["mysql", "db"], "pip": [("mysqlclient", ">=2.2,<2.3")]},
    {"id": "kafka_runtime", "display_name": "Kafka Runtime", "category": "infra", "block_kind": "runtime", "tags": ["kafka", "streaming"], "pip": [("confluent-kafka", ">=2.6,<2.8")]},
    {"id": "rabbitmq_runtime", "display_name": "RabbitMQ Runtime", "category": "infra", "block_kind": "runtime", "tags": ["rabbitmq", "queue"], "pip": [("pika", ">=1.3,<1.4")]},
    {"id": "s3_runtime", "display_name": "S3 Runtime", "category": "infra", "block_kind": "runtime", "tags": ["storage", "s3"], "pip": [("boto3", ">=1.35,<1.37")]},
    {"id": "azure_blob_runtime", "display_name": "Azure Blob Runtime", "category": "infra", "block_kind": "runtime", "tags": ["storage", "azure"], "pip": [("azure-storage-blob", ">=12.23,<12.24")]},
    {"id": "gcs_runtime", "display_name": "GCS Runtime", "category": "infra", "block_kind": "runtime", "tags": ["storage", "gcp"], "pip": [("google-cloud-storage", ">=2.18,<2.20")]},
    {"id": "jwt_auth", "display_name": "JWT Auth Helpers", "category": "infra", "block_kind": "runtime", "tags": ["auth", "security"], "pip": [("pyjwt", ">=2.9,<2.11"), ("cryptography", ">=43,<45")]},
    {"id": "oauth_runtime", "display_name": "OAuth Runtime", "category": "infra", "block_kind": "runtime", "tags": ["auth", "oauth"], "pip": [("authlib", ">=1.3,<1.4")]},
    {"id": "ros2_runtime", "display_name": "ROS2 Runtime (Pilot)", "category": "robotics_edge", "block_kind": "runtime", "tags": ["robotics", "edge", "pilot"], "pip": [("rclpy", ">=3.4,<3.6")]},
    {"id": "gstreamer_pipeline", "display_name": "GStreamer Pipeline (Pilot)", "category": "robotics_edge", "block_kind": "runtime", "tags": ["robotics", "video", "pilot"], "pip": [("PyGObject", ">=3.48,<3.50")]},
    {"id": "jetson_helpers", "display_name": "Jetson Helpers (Pilot)", "category": "robotics_edge", "block_kind": "accelerator", "tags": ["robotics", "jetson", "pilot"], "pip": [("jetson-stats", ">=4.2,<4.3")]},
    {"id": "realsense_runtime", "display_name": "RealSense Runtime (Pilot)", "category": "robotics_edge", "block_kind": "runtime", "tags": ["robotics", "camera", "pilot"], "pip": [("pyrealsense2", ">=2.56,<2.57")]},
]

def _to_pip(items: list[tuple[str, str]]) -> list[BlockPresetPipDep]:
    return [BlockPresetPipDep(name=name, version=version) for name, version in items]


def _base_preset_to_model(row: dict[str, object]) -> BlockPreset:
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
            layers = ["model_runtime_layer"]
        if category in {"infra"}:
            layers.append("system_runtime_layer")
        if category in {"robotics_edge"}:
            layers = ["application_orchestration_layer", "model_runtime_layer"]
        if category in {"observability"}:
            layers = ["observability_operations_layer"]
    provides = {
        "preset_group": base_id,
    }
    return BlockPreset(
        id=base_id,
        display_name=str(row["display_name"]),
        description=f"Opinionated preset for {row['display_name']}.",
        category=str(row["category"]),
        tags=list(row.get("tags", [])) if manual else [*list(row.get("tags", [])), "preset"],
        pip=_to_pip(list(row.get("pip", []))),
        apt=list(row.get("apt", [])),
        env={} if manual else {"STACKSMITH_PROFILE": "balanced"},
        ports=[] if manual else ports,
        entrypoint_cmd=[] if manual else (["python", "-m", "uvicorn"] if str(row["block_kind"]) == "api" else []),
        requires=requires,
        provides=provides,
        layers=layers,
    )


def default_block_catalog() -> BlockPresetCatalog:
    categories = [
        BlockPresetCategory(id=cid, label=label, description=description)
        for cid, label, description in _CATEGORY_ROWS
    ]
    presets = [_base_preset_to_model(row) for row in _BASE_PRESETS]
    return BlockPresetCatalog(
        schema_version=1,
        revision=1,
        categories=categories,
        presets=presets,
    )


def load_block_catalog(path: Path | None = None) -> BlockPresetCatalog:
    target = path or block_catalog_path()
    base = default_block_catalog()
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
    return BlockPresetCatalog.model_validate(merged)

