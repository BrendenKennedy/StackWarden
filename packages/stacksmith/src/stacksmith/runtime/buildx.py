"""Buildx CLI wrapper — CLI only, never use the Docker SDK for builds.

Shells out to ``docker buildx build`` to produce images.  The SDK is
intentionally NOT used for build operations to maintain a clean boundary.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
import time
from queue import Empty, Queue
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

log = logging.getLogger(__name__)


class BuildxError(Exception):
    def __init__(self, returncode: int, stderr: str) -> None:
        self.returncode = returncode
        self.stderr = stderr
        truncated = stderr[:500] + ("..." if len(stderr) > 500 else "")
        super().__init__(f"buildx exited {returncode}: {truncated}")


def build(
    *,
    context_dir: str | Path,
    dockerfile: str | Path | None = None,
    tags: list[str] | None = None,
    platform: str | None = None,
    build_args: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
    extra_flags: list[str] | None = None,
    load: bool = True,
    timeout: int = 3600,
    retry_on_oom: bool = True,
) -> str:
    """Run ``docker buildx build`` and return stdout (contains image id when using --load).

    Parameters
    ----------
    context_dir:
        Build context directory.
    dockerfile:
        Path to the Dockerfile (relative to context_dir, or absolute).
    tags:
        Image tags to apply (``-t`` flags).
    platform:
        Target platform, e.g. ``linux/arm64``.  Single-platform only in v1.
    build_args:
        ``--build-arg`` key=value pairs.
    labels:
        ``--label`` key=value pairs (stacksmith metadata injected here).
    load:
        If *True*, pass ``--load`` to push the image into the local daemon.
    """
    cmd: list[str] = ["docker", "buildx", "build"]

    if dockerfile:
        cmd += ["-f", str(dockerfile)]
    if platform:
        cmd += ["--platform", platform]
    if load:
        cmd.append("--load")
    for tag in tags or []:
        cmd += ["-t", tag]
    for k, v in (build_args or {}).items():
        cmd += ["--build-arg", f"{k}={v}"]
    for k, v in (labels or {}).items():
        cmd += ["--label", f"{k}={v}"]
    if extra_flags:
        cmd += list(extra_flags)

    cmd.append(str(context_dir))

    # Redact --build-arg values in logged output to avoid leaking secrets
    redacted = []
    i = 0
    while i < len(cmd):
        if cmd[i] == "--build-arg" and i + 1 < len(cmd):
            key = cmd[i + 1].split("=", 1)[0]
            redacted.append(cmd[i])
            redacted.append(f"{key}=<REDACTED>")
            i += 2
        else:
            redacted.append(cmd[i])
            i += 1
    log.info("Running: %s", shlex.join(redacted))

    result = _run_streaming(cmd, timeout=timeout)
    if result.returncode != 0 and retry_on_oom and _looks_like_oom(result.stderr):
        retry_cmd = _retry_cmd_with_lower_parallelism(cmd)
        if retry_cmd != cmd:
            log.warning("buildx appears OOM-constrained; retrying with lower build parallelism")
            result = _run_streaming(retry_cmd, timeout=timeout)

    if result.returncode != 0:
        log.error("buildx stderr:\n%s", result.stderr)
        raise BuildxError(result.returncode, result.stderr)

    log.debug("buildx stdout:\n%s", result.stdout)
    return result.stdout.strip()


def is_available() -> tuple[bool, str]:
    """Check if ``docker buildx`` is available and return (ok, version_string)."""
    try:
        result = subprocess.run(
            ["docker", "buildx", "version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "docker command not found"


def _looks_like_oom(stderr: str) -> bool:
    haystack = stderr.lower()
    markers = (
        "out of memory",
        "cannot allocate memory",
        "killed",
        "oom",
        "exit code: 137",
    )
    return any(marker in haystack for marker in markers)


def _retry_cmd_with_lower_parallelism(cmd: list[str]) -> list[str]:
    """Return a modified command with reduced STACKSMITH_BUILD_JOBS when present."""
    updated = list(cmd)
    for i, token in enumerate(updated):
        if token != "--build-arg" or i + 1 >= len(updated):
            continue
        arg = updated[i + 1]
        if not arg.startswith("STACKSMITH_BUILD_JOBS="):
            continue
        value = arg.split("=", 1)[1]
        try:
            jobs = int(value)
        except ValueError:
            return updated
        lowered = max(1, jobs // 2)
        if lowered == jobs:
            return updated
        updated[i + 1] = f"STACKSMITH_BUILD_JOBS={lowered}"
        return updated
    return updated


def _run_streaming(cmd: list[str], *, timeout: int) -> SimpleNamespace:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        raise BuildxError(1, "failed to open buildx output stream")

    queue: Queue[str | None] = Queue()

    def _reader() -> None:
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            queue.put(line)
        queue.put(None)

    reader = Thread(target=_reader, daemon=True)
    reader.start()
    started = time.monotonic()
    output_lines: list[str] = []
    stream_closed = False

    while True:
        if time.monotonic() - started > timeout:
            proc.kill()
            proc.wait(timeout=5)
            raise BuildxError(124, f"buildx timed out after {timeout}s")
        try:
            line = queue.get(timeout=0.2)
        except Empty:
            if proc.poll() is not None and stream_closed:
                break
            continue
        if line is None:
            stream_closed = True
            if proc.poll() is not None:
                break
            continue
        output_lines.append(line)
        text = line.rstrip()
        if text:
            log.info("[buildx] %s", text)

    combined = "".join(output_lines)
    return SimpleNamespace(
        returncode=proc.returncode or 0,
        stdout=combined,
        stderr=combined,
    )
