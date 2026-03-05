"""Coverage tests for jobs, plan, verify, and artifacts routes."""

from __future__ import annotations

import json
import os
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stacksmith.domain.enums import ArtifactStatus
from stacksmith.domain.models import ArtifactRecord, Plan, PlanArtifact, PlanDecision, PlanStep
from stacksmith.domain.verify import VerifyReport
from stacksmith.web.jobs.models import JobStatus


@pytest.fixture()
def client_bundle(tmp_path):
    (tmp_path / "stacks").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "blocks").mkdir()
    with patch.dict(
        os.environ,
        {
            "STACKSMITH_DATA_DIR": str(tmp_path),
            "STACKSMITH_WEB_DEV": "true",
            "STACKSMITH_TUPLE_LAYER_MODE": "off",
        },
    ):
        from stacksmith.catalog.store import CatalogStore
        from stacksmith.web.app import create_app
        from stacksmith.web.deps import get_catalog, get_job_manager
        from stacksmith.web.jobs.manager import JobManager
        from stacksmith.web.jobs.store import JobStore
        from stacksmith.web.settings import WebSettings

        catalog = CatalogStore(db_path=tmp_path / "catalog.sqlite3")
        manager = JobManager(store=JobStore(db_path=tmp_path / "catalog.sqlite3"))
        app = create_app(WebSettings(token=None, dev=True))
        app.dependency_overrides[get_catalog] = lambda: catalog
        app.dependency_overrides[get_job_manager] = lambda: manager
        yield TestClient(app), catalog, manager


def test_jobs_endpoints_cover_queue_detail_cancel_events_and_ensure(client_bundle, monkeypatch):
    client, _catalog, manager = client_bundle

    # Seed one job for list/detail/cancel/events checks.
    seeded = manager.create_job(profile_id="p-seeded", stack_id="s-seeded", variants=None, flags={})

    list_resp = client.get("/api/jobs")
    assert list_resp.status_code == 200
    assert any(row["job_id"] == seeded.job_id for row in list_resp.json())

    detail_resp = client.get(f"/api/jobs/{seeded.job_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["job_id"] == seeded.job_id
    assert detail_resp.json()["build_optimization"] == {}

    events_resp = client.get("/api/jobs/missing/events")
    assert events_resp.status_code == 404

    cancel_resp = client.post(f"/api/jobs/{seeded.job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["canceled"] is True
    assert cancel_resp.json()["job_id"] == seeded.job_id

    # Cover /api/ensure with lightweight monkeypatches (no resolver/build execution).
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.load_profile",
        lambda _: SimpleNamespace(host_facts=SimpleNamespace(memory_gb_total=None)),
    )
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_stack", lambda _: SimpleNamespace(blocks=[]))
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_block", lambda _: object())
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.resolve",
        lambda *args, **kwargs: SimpleNamespace(decision=SimpleNamespace(build_optimization=None)),
    )
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.decide_admission",
        lambda **_kwargs: SimpleNamespace(allowed=True, detail="ok"),
    )
    async def _fake_run_ensure_job(*_args, **_kwargs):
        return None
    monkeypatch.setattr("stacksmith.web.routes.jobs.run_ensure_job", _fake_run_ensure_job)

    ensure_resp = client.post(
        "/api/ensure",
        json={"profile_id": "p-new", "stack_id": "s-new", "variants": {}, "flags": {}},
    )
    assert ensure_resp.status_code == 200
    assert ensure_resp.json()["job_id"]


def test_ensure_rejects_when_admission_denies(client_bundle, monkeypatch):
    client, _catalog, _manager = client_bundle
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.load_profile",
        lambda _: SimpleNamespace(host_facts=SimpleNamespace(memory_gb_total=8.0)),
    )
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_stack", lambda _: SimpleNamespace(blocks=[]))
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_block", lambda _: object())
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.resolve",
        lambda *args, **kwargs: SimpleNamespace(decision=SimpleNamespace(build_optimization=None)),
    )
    monkeypatch.setattr(
        "stacksmith.web.routes.jobs.decide_admission",
        lambda **_kwargs: SimpleNamespace(allowed=False, detail="busy"),
    )
    resp = client.post(
        "/api/ensure",
        json={"profile_id": "p-new", "stack_id": "s-new", "variants": {}, "flags": {}},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"] == "busy"


def test_run_ensure_job_respects_pre_start_cancel(client_bundle, monkeypatch):
    _client, _catalog, manager = client_bundle
    record = manager.create_job(profile_id="p-cancel", stack_id="s-cancel", variants=None, flags={})
    assert manager.request_cancel(record.job_id) is True

    called = {"ran": False}

    def _never_run(*_args, **_kwargs):
        called["ran"] = True
        raise AssertionError("ensure sync path should not run for pre-canceled jobs")

    monkeypatch.setattr("stacksmith.web.jobs.runners._run_ensure_sync", _never_run)
    from stacksmith.web.jobs.runners import run_ensure_job

    asyncio.run(run_ensure_job(record, manager))
    fresh = manager.get_job(record.job_id)
    assert fresh is not None
    assert fresh.status == JobStatus.CANCELED
    assert called["ran"] is False


def test_run_ensure_job_fails_when_artifact_is_failed(client_bundle, monkeypatch):
    _client, _catalog, manager = client_bundle
    record = manager.create_job(profile_id="p-fail", stack_id="s-fail", variants=None, flags={})

    failed_artifact = ArtifactRecord(
        id="artifact-failed",
        profile_id="p-fail",
        stack_id="s-fail",
        tag="local/stacksmith:failed",
        fingerprint="f" * 64,
        base_image="python:3.12",
        build_strategy="overlay",
        status=ArtifactStatus.FAILED,
        error_detail="hook failure",
    )

    monkeypatch.setattr(
        "stacksmith.web.jobs.runners._run_ensure_sync",
        lambda *_args, **_kwargs: (failed_artifact, None),
    )
    from stacksmith.web.jobs.runners import run_ensure_job

    asyncio.run(run_ensure_job(record, manager))
    fresh = manager.get_job(record.job_id)
    assert fresh is not None
    assert fresh.status == JobStatus.FAILED
    assert fresh.result_artifact_id == "artifact-failed"


def test_plan_verify_and_artifacts_route_coverage(client_bundle, monkeypatch):
    client, catalog, _manager = client_bundle
    fingerprint = "a" * 64

    # /api/plan (fully mocked plan resolution path)
    plan_obj = Plan(
        plan_id="plan_test",
        profile_id="profile_test",
        stack_id="stack_test",
        decision=PlanDecision(base_image="python:3.12-slim", builder="overlay"),
        steps=[PlanStep(type="pull", image="python:3.12-slim")],
        artifact=PlanArtifact(tag="local/stacksmith:test", fingerprint=fingerprint),
    )
    monkeypatch.setattr("stacksmith.web.routes.plan.load_profile", lambda _: object())
    monkeypatch.setattr("stacksmith.web.routes.plan.load_stack", lambda _: SimpleNamespace(blocks=[]))
    monkeypatch.setattr("stacksmith.web.routes.plan.load_block", lambda _: object())
    monkeypatch.setattr("stacksmith.web.routes.plan.resolve", lambda *args, **kwargs: plan_obj)

    plan_resp = client.post(
        "/api/plan",
        json={"profile_id": "profile_test", "stack_id": "stack_test", "variants": {}, "flags": {}},
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json()["plan_id"] == "plan_test"

    # /api/verify (mock docker + verification/fix behavior)
    monkeypatch.setattr("stacksmith.web.routes.verify.DockerClient", lambda: object())
    monkeypatch.setattr(
        "stacksmith.web.routes.verify.verify_artifact",
        lambda *args, **kwargs: VerifyReport(ok=False, errors=["mismatch"], warnings=[], facts={}),
    )
    monkeypatch.setattr(
        "stacksmith.web.routes.verify.apply_fix",
        lambda *_args, **_kwargs: ["marked stale"],
    )
    verify_resp = client.post("/api/verify", json={"tag_or_id": "anything", "strict": False, "fix": True})
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert verify_body["ok"] is False
    assert verify_body["actions"] == ["marked stale"]

    # Seed catalog artifact for /api/artifacts* coverage.
    record = ArtifactRecord(
        id="artifact_test",
        profile_id="profile_test",
        stack_id="stack_test",
        tag="local/stacksmith:test",
        fingerprint=fingerprint,
        base_image="python:3.12-slim",
        build_strategy="overlay",
        status=ArtifactStatus.BUILT,
        created_at=datetime.now(timezone.utc),
    )
    catalog.insert_artifact(record)

    from stacksmith.domain.snapshots import artifact_dir

    art_dir = artifact_dir(record.fingerprint)
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "plan.json").write_text(json.dumps({"plan_id": "plan_test"}), encoding="utf-8")

    list_resp = client.get("/api/artifacts")
    assert list_resp.status_code == 200
    assert any(row["id"] == "artifact_test" for row in list_resp.json())

    detail_resp = client.get("/api/artifacts/artifact_test")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == "artifact_test"

    file_resp = client.get("/api/artifacts/artifact_test/files/plan")
    assert file_resp.status_code == 200
    assert file_resp.json()["plan_id"] == "plan_test"

    stale_resp = client.post("/api/artifacts/artifact_test/mark-stale")
    assert stale_resp.status_code == 200
    assert stale_resp.json()["marked"] >= 1

    # Create another artifact for delete test (stale_resp mutates catalog)
    catalog.insert_artifact(
        ArtifactRecord(
            id="artifact_delete_test",
            profile_id="profile_test",
            stack_id="stack_test",
            tag="local/stacksmith:delete-test",
            fingerprint="fp_delete",
            base_image="python:3.12",
            build_strategy="overlay",
            status=ArtifactStatus.STALE,
            created_at=datetime.now(timezone.utc),
        )
    )
    del_resp = client.delete("/api/artifacts/artifact_delete_test")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
    missing = client.get("/api/artifacts/artifact_delete_test")
    assert missing.status_code == 404


def test_compatibility_fix_endpoints(client_bundle, monkeypatch):
    """Cover GET /jobs/{id}/compatibility-fix and POST /jobs/{id}/retry-with-fix."""
    client, _catalog, manager = client_bundle

    # Create a failed job with pip conflict error
    record = manager.create_job(
        profile_id="p-fail",
        stack_id="s-fail",
        variants=None,
        flags={"rebuild": True},
    )
    record.status = JobStatus.FAILED
    record.error_message = "Build failed: ResolutionImpossible. The conflict is caused by: vllm requires setuptools<77"
    manager.update_job(record)

    # Mock load_profile, load_stack, load_block, resolve for compatibility-fix analysis
    plan_obj = SimpleNamespace(
        decision=SimpleNamespace(base_image="nvcr.io/nvidia/pytorch:25.03-py3"),
    )
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_profile", lambda _: object())
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_stack", lambda _: SimpleNamespace(blocks=[]))
    monkeypatch.setattr("stacksmith.web.routes.jobs.load_block", lambda _: object())
    monkeypatch.setattr("stacksmith.web.routes.jobs.resolve", lambda *args, **kwargs: plan_obj)

    # GET compatibility-fix
    fix_resp = client.get(f"/api/jobs/{record.job_id}/compatibility-fix")
    assert fix_resp.status_code == 200
    fix_body = fix_resp.json()
    assert fix_body["applicable"] is True
    assert "vllm" in fix_body["suggested_overrides"]
    assert "setuptools" in fix_body["suggested_overrides"]

    # POST retry-with-fix (mock run_ensure_job so we don't actually run a build)
    async def _fake_run(*_args, **_kwargs):
        return None

    monkeypatch.setattr("stacksmith.web.routes.jobs.run_ensure_job", _fake_run)

    retry_resp = client.post(f"/api/jobs/{record.job_id}/retry-with-fix")
    assert retry_resp.status_code == 200
    retry_body = retry_resp.json()
    assert "job_id" in retry_body
    assert retry_body["applied"] is True
    assert retry_body["job_id"] != record.job_id

    # Non-failed job: compatibility-fix returns applicable=False
    success_job = manager.create_job(profile_id="p-ok", stack_id="s-ok", variants=None, flags={})
    success_resp = client.get(f"/api/jobs/{success_job.job_id}/compatibility-fix")
    assert success_resp.status_code == 200
    assert success_resp.json()["applicable"] is False

    # Non-failed job: retry-with-fix returns 400
    retry_fail_resp = client.post(f"/api/jobs/{success_job.job_id}/retry-with-fix")
    assert retry_fail_resp.status_code == 400

    # POST retry (simple retry without fix) - works for any failed job
    simple_retry_resp = client.post(f"/api/jobs/{record.job_id}/retry")
    assert simple_retry_resp.status_code == 200
    simple_retry_body = simple_retry_resp.json()
    assert "job_id" in simple_retry_body
    assert simple_retry_body["job_id"] != record.job_id

    # Non-failed job: retry returns 400
    simple_retry_fail_resp = client.post(f"/api/jobs/{success_job.job_id}/retry")
    assert simple_retry_fail_resp.status_code == 400
