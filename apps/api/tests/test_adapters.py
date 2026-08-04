import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import worker
from app.adapters.providers import OpenAICompatibleAgentAdapter, StructuredLLMExtractor
from app.adapters.tau_sync import TASK_IDS, normalize_retail_tasks
from app.config import Settings
from app.db import Base
from app.models import Job
from app.services.errors import ServiceError
from app.services.seed import seed_demo


def test_hosted_postgres_urls_use_async_dialect() -> None:
    assert Settings(database_url="postgres://user:pass@db.example/app").database_url == (
        "postgresql+asyncpg://user:pass@db.example/app"
    )
    assert Settings(database_url="postgresql://user:pass@db.example/app").database_url == (
        "postgresql+asyncpg://user:pass@db.example/app"
    )
    settings = Settings(
        database_url="postgresql://user:pass@db.example/app?sslmode=require&application_name=api",
        migration_database_url="postgresql://user:pass@db.example/app?sslmode=require",
    )
    assert settings.database_url.endswith("?ssl=require&application_name=api")
    assert settings.migration_database_url.endswith("?sslmode=require")


def test_data_root_can_be_configured_explicitly(tmp_path) -> None:
    assert Settings(data_root=tmp_path).data_root == tmp_path


def test_tau_manifest_normalizes_exact_reviewed_ids() -> None:
    fake = [
        {
            "id": str(task_id),
            "user_scenario": {"instructions": {"reason_for_call": f"Purpose {task_id}"}},
            "initial_state": None,
            "evaluation_criteria": {"actions": [{"name": "get_order_details"}]},
        }
        for task_id in TASK_IDS
    ]
    result = normalize_retail_tasks(fake)
    assert result["task_count"] == 17
    assert [task["upstream_task_id"] for task in result["tasks"]] == [str(value) for value in TASK_IDS]
    assert all(task["provenance"]["upstream_path"].endswith("tasks.json") for task in result["tasks"])


def test_tau_normalizer_rejects_missing_manifest_task() -> None:
    with pytest.raises(RuntimeError, match="missing manifest tasks"):
        normalize_retail_tasks([])


@pytest.mark.asyncio
async def test_optional_adapters_fail_gracefully_without_credentials() -> None:
    extractor = StructuredLLMExtractor(api_key="", model="test")
    agent = OpenAICompatibleAgentAdapter(api_key="", base_url="https://example.invalid", model="test")
    with pytest.raises(ServiceError) as extraction:
        await extractor.extract([])
    with pytest.raises(ServiceError) as execution:
        await agent.trajectory({})
    assert extraction.value.code == "live_extractor_not_configured"
    assert execution.value.code == "live_agent_not_configured"


@pytest.mark.asyncio
async def test_sql_worker_claims_and_completes_supported_job(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", maker)
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: type("WorkerSettings", (), {"database_url": "sqlite+aiosqlite:///worker.db", "worker_lease_seconds": 60})(),
    )
    async with maker() as session:
        project = await seed_demo(session)
        job = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind="analyze",
            payload={"project_id": project.id},
            idempotency_key="worker-test",
            request_fingerprint="0" * 64,
            status="queued",
            progress=0,
        )
        second = Job(
            workspace_id=project.workspace_id,
            project_id=project.id,
            kind="analyze",
            payload={"project_id": project.id},
            idempotency_key="worker-test-2",
            request_fingerprint="1" * 64,
            status="queued",
            progress=0,
        )
        session.add_all([job, second])
        await session.commit()
        job_id = job.id
    claimed = await worker.claim_one()
    assert claimed and claimed.status == "running" and claimed.attempt_count == 1
    assert await worker.claim_one() is None
    await worker.process_job(job_id, expected_owner="expired-owner")
    async with maker() as session:
        still_owned = await session.get(Job, job_id)
        assert still_owned and still_owned.status == "running"
        assert still_owned.owner == claimed.owner
    await worker.process_job(job_id, expected_owner=claimed.owner)
    async with maker() as session:
        completed = await session.get(Job, job_id)
        assert completed and completed.status == "succeeded"
        assert completed.progress == 100 and completed.resource_id == project.id
    await engine.dispose()
