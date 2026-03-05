"""StackWarden stub service."""
from fastapi import FastAPI
app = FastAPI(title="StackWarden Stub")

@app.get("/health")
def health():
    return {"status": "ok"}
