"""Stacksmith stub service."""
from fastapi import FastAPI
app = FastAPI(title="Stacksmith Stub")

@app.get("/health")
def health():
    return {"status": "ok"}
