"""Flux Schnell inference API — HTTP wrapper for ComfyUI custom nodes.

Serves FLUX.1-schnell via FastAPI. ComfyUI custom nodes can call this
container over HTTP to generate images.

Usage from ComfyUI:
  POST /generate
  Body: {"prompt": "...", "height": 768, "width": 1360, "num_inference_steps": 4}
"""
from __future__ import annotations

import io
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Lazy-load pipeline to avoid import at module load (GPU memory)
_pipe = None


def _get_pipeline():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import FluxPipeline

        _pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.bfloat16,
        )
        _pipe.enable_model_cpu_offload()
    return _pipe


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload on startup (optional — remove for lazy load)
    # _get_pipeline()
    yield
    global _pipe
    _pipe = None


app = FastAPI(
    title="Flux Schnell Inference API",
    description="HTTP API for FLUX.1-schnell — call from ComfyUI custom nodes",
    lifespan=lifespan,
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    height: int = Field(default=768, ge=256, le=2048)
    width: int = Field(default=1360, ge=256, le=2048)
    num_inference_steps: int = Field(default=4, ge=1, le=20)
    seed: int | None = Field(default=None, description="Random seed for reproducibility")


@app.get("/health")
def health():
    return {"status": "ok", "model": "FLUX.1-schnell"}


@app.post("/generate")
def generate(req: GenerateRequest):
    """Generate image from text prompt. Returns PNG bytes."""
    pipe = _get_pipeline()
    generator = None
    if req.seed is not None:
        import torch
        generator = torch.Generator("cpu").manual_seed(req.seed)

    try:
        out = pipe(
            prompt=req.prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=0.0,  # Required for Schnell
            max_sequence_length=256,
            generator=generator,
        )
        image = out.images[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.post("/generate/json")
def generate_json(req: GenerateRequest):
    """Generate and return base64-encoded PNG (for JSON responses)."""
    import base64

    pipe = _get_pipeline()
    generator = None
    if req.seed is not None:
        import torch
        generator = torch.Generator("cpu").manual_seed(req.seed)

    try:
        out = pipe(
            prompt=req.prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=0.0,
            max_sequence_length=256,
            generator=generator,
        )
        image = out.images[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"image": b64, "format": "png"}
