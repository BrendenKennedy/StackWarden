"""Enumeration types for Stacksmith domain models."""

from enum import Enum


class Arch(str, Enum):
    ARM64 = "arm64"
    AMD64 = "amd64"


class ContainerRuntime(str, Enum):
    NVIDIA = "nvidia"
    RUNC = "runc"


class TaskType(str, Enum):
    DIFFUSION = "diffusion"
    LLM = "llm"
    EMBEDDING = "embedding"
    VISION = "vision"
    ASR = "asr"
    TTS = "tts"
    CUSTOM = "custom"


class ServeType(str, Enum):
    PYTHON_API = "python_api"
    TRITON = "triton"
    VLLM = "vllm"
    CUSTOM = "custom"


class ApiType(str, Enum):
    FASTAPI = "fastapi"
    GRPC = "grpc"
    NONE = "none"
    CUSTOM = "custom"


class BuildStrategy(str, Enum):
    PULL = "pull"
    OVERLAY = "overlay"
    DOCKERFILE_TEMPLATE = "dockerfile_template"
    CUSTOM = "custom"


class ArtifactStatus(str, Enum):
    PLANNED = "planned"
    BUILDING = "building"
    BUILT = "built"
    FAILED = "failed"
    STALE = "stale"


class LicenseSeverity(str, Enum):
    OK = "ok"
    REVIEW = "review"
    RESTRICTED = "restricted"
