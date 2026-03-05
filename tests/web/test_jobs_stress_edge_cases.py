"""Additional stress edge-case coverage for web jobs endpoints."""

from __future__ import annotations

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stackwarden.web.jobs.models import JobEvent, JobStatus


@pytest.fixture()
def client_bundle(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    with patch.dict(
        os.environ,
        {
            "STACKWARDEN_DATA_DIR": str(tmp_path),
            "STACKWARDEN_WEB_DEV": "true",
            "STACKWARDEN_TUPLE_LAYER_MODE": "off",
        },
    ):
        from stackwarden.catalog.store import CatalogStore
        from stackwarden.web.app import create_app
        from stackwarden.web.deps import get_catalog, get_job_manager
        from stackwarden.web.jobs.manager import JobManager
        from stackwarden.web.jobs.store import JobStore
        from stackwarden.web.settings import WebSettings

        catalog = CatalogStore(db_path=tmp_path / "catalog.sqlite3")
        manager = JobManager(store=JobStore(db_path=tmp_path / "catalog.sqlite3"))
        app = create_app(WebSettings(token=None, dev=True))
        app.dependency_overrides[get_catalog] = lambda: catalog
        app.dependency_overrides[get_job_manager] = lambda: manager
        yield TestClient(app), catalog, manager


def test_plan_and_ensure_reject_unknown_flags(client_bundle):
    client, _catalog, _manager = client_bundle

    plan_resp = client.post(
        "/api/plan",
        json={
            "profile_id": "p1",
            "stack_id": "s1",
            "variants": {},
            "flags": {"explain": True, "unknown_flag": True},
        },
    )
    assert plan_resp.status_code == 422

    ensure_resp = client.post(
        "/api/ensure",
        json={
            "profile_id": "p1",
            "stack_id": "s1",
            "variants": {},
            "flags": {"rebuild": True, "surprise": True},
        },
    )
    assert ensure_resp.status_code == 422


def test_concurrent_ensure_requests_apply_admission_control(client_bundle, monkeypatch):
    client, _catalog, _manager = client_bundle

    monkeypatch.setattr(
        "stackwarden.web.routes.jobs.load_profile",
        lambda _: SimpleNamespace(host_facts=SimpleNamespace(memory_gb_total=16.0)),
    )
    monkeypatch.setattr("stackwarden.web.routes.jobs.load_stack", lambda _: SimpleNamespace(blocks=[]))
    monkeypatch.setattr("stackwarden.web.routes.jobs.load_block", lambda _: object())
    monkeypatch.setattr(
        "stackwarden.web.routes.jobs.resolve",
        lambda *args, **kwargs: SimpleNamespace(decision=SimpleNamespace(build_optimization=None)),
    )

    # Permit only one active build at a time to stress admission decisions.
    gate = {"calls": 0}

    def _admission_gate(**_kwargs):
        gate["calls"] += 1
        return SimpleNamespace(allowed=gate["calls"] == 1, detail="busy")

    monkeypatch.setattr("stackwarden.web.routes.jobs.decide_admission", _admission_gate)

    async def _slow_job(*_args, **_kwargs):
        await asyncio.sleep(0.2)

    monkeypatch.setattr("stackwarden.web.routes.jobs.run_ensure_job", _slow_job)

    first = client.post(
        "/api/ensure",
        json={"profile_id": "p1", "stack_id": "s1", "variants": {}, "flags": {}},
    )
    assert first.status_code == 200

    # While the first background job is still active, admission should reject new ones.
    second = client.post(
        "/api/ensure",
        json={"profile_id": "p1", "stack_id": "s1", "variants": {}, "flags": {}},
    )
    assert second.status_code == 429


def test_cancel_endpoint_is_stable_under_race(client_bundle):
    client, _catalog, manager = client_bundle
    record = manager.create_job(profile_id="p-race", stack_id="s-race", variants=None, flags={})

    def cancel_once() -> bool:
        resp = client.post(f"/api/jobs/{record.job_id}/cancel")
        assert resp.status_code == 200
        return bool(resp.json().get("canceled"))

    with ThreadPoolExecutor(max_workers=10) as ex:
        outcomes = list(ex.map(lambda _i: cancel_once(), range(10)))

    assert any(outcomes)
    fresh = manager.get_job(record.job_id)
    assert fresh is not None
    assert fresh.status == JobStatus.CANCELED


def test_sse_events_reach_multiple_subscribers(client_bundle):
    client, _catalog, manager = client_bundle
    record = manager.create_job(profile_id="p-stream", stack_id="s-stream", variants=None, flags={})

    def consume_events() -> str:
        lines: list[str] = []
        with client.stream("GET", f"/api/jobs/{record.job_id}/events") as response:
            assert response.status_code == 200
            for line in response.iter_lines():
                if not line:
                    continue
                value = line.decode() if isinstance(line, bytes) else line
                lines.append(value)
        return "\n".join(lines)

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_a = ex.submit(consume_events)
        fut_b = ex.submit(consume_events)
        time.sleep(0.05)
        manager.publish_event(
            record.job_id,
            JobEvent(
                type="status",
                ts=datetime.now(timezone.utc),
                payload=json.dumps({"status": "running"}),
            ),
        )
        manager.publish_event(
            record.job_id,
            JobEvent(
                type="log",
                ts=datetime.now(timezone.utc),
                payload="line-1",
            ),
        )
        manager.publish_sentinel(record.job_id)
        out_a = fut_a.result(timeout=3)
        out_b = fut_b.result(timeout=3)

    for output in (out_a, out_b):
        assert "event: status" in output
        assert "event: log" in output
