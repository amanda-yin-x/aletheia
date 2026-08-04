from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Report, Run
from app.services.compiler import compile_project
from app.services.errors import ServiceError
from app.services.reporting import create_report
from app.services.runner import run_comparison
from app.services.seed import seed_demo
from app.tenancy import LOCAL_WORKSPACE_ID

cli = typer.Typer(help="Aletheia Policy CI — compile policies and test releases.", no_args_is_help=True)
db_cli = typer.Typer(help="Migrate the application database with Alembic.")
demo_cli = typer.Typer(help="Manage the deterministic Northstar workspace.")
benchmark_cli = typer.Typer(help="Manage the optional pinned Retail-17 import adapter.")
cli.add_typer(db_cli, name="db")
cli.add_typer(demo_cli, name="demo")
cli.add_typer(benchmark_cli, name="benchmark")


async def _project(slug: str) -> Project:
    async with SessionLocal() as session:
        project = await session.scalar(
            select(Project).where(
                Project.workspace_id == LOCAL_WORKSPACE_ID, Project.slug == slug
            )
        )
        if not project:
            raise ServiceError("project_not_found", f"Project {slug!r} was not found.")
        return project


@db_cli.command("upgrade")
def db_upgrade() -> None:
    """Upgrade the database to the immutable Alembic head revision."""
    from app.deploy import migrate_database

    migrate_database()
    typer.echo("Database schema is current.")


@demo_cli.command("seed")
def demo_seed(reset: bool = typer.Option(False, "--reset", help="Replace the existing evaluation workspace."), json_output: bool = typer.Option(False, "--json")) -> None:
    """Seed the Northstar Retail evaluation workspace."""
    async def run() -> Project:
        async with SessionLocal() as session:
            return await seed_demo(session, reset=reset)
    project = asyncio.run(run())
    output = {"project_id": project.id, "slug": project.slug, "mode": project.mode}
    typer.echo(json.dumps(output, sort_keys=True) if json_output else f"Seeded {project.name} ({project.id})")


@cli.command("analyze")
def analyze(project: str = typer.Option("northstar-retail"), extractor: str = typer.Option("fixture"), json_output: bool = typer.Option(False, "--json")) -> None:
    """Load bundled source-linked candidates and deterministic findings."""
    if extractor != "fixture":
        raise typer.BadParameter("The optional structured LLM extractor is not configured. Use the deterministic replay adapter (`fixture`).")
    target = asyncio.run(_project(project))
    output = {"project_id": target.id, "extractor": "fixture", "status": "fixture_available", "publication": "human_review_required"}
    typer.echo(json.dumps(output, sort_keys=True) if json_output else "Bundled evaluation candidates loaded; no analyzer or model ran.")


@cli.command("compile")
def compile_command(project: str = typer.Option("northstar-retail"), json_output: bool = typer.Option(False, "--json")) -> None:
    """Compile approved revisions into a byte-addressed stored artifact bundle."""
    async def run() -> object:
        target = await _project(project)
        async with SessionLocal() as session:
            return await compile_project(session, target.id)
    try:
        build = asyncio.run(run())
    except ServiceError as error:
        typer.echo(f"{error.code}: {error.message}", err=True)
        raise typer.Exit(1) from error
    output = {"build_id": build.id, "hash": build.content_hash, "stats": build.stats}  # type: ignore[attr-defined]
    typer.echo(json.dumps(output, sort_keys=True) if json_output else f"Build {build.id} {build.content_hash}")  # type: ignore[attr-defined]


@cli.command("test")
def test_command(project: str = typer.Option("northstar-retail"), adapter: str = typer.Option("fixture"), arms: str = typer.Option("all"), json_output: bool = typer.Option(False, "--json")) -> None:
    """Run the deterministic comparison from identical initial state."""
    if adapter != "fixture" or arms != "all":
        raise typer.BadParameter("The no-key workspace supports adapter=fixture and arms=all.")
    async def run() -> Run:
        target = await _project(project)
        async with SessionLocal() as session:
            return await run_comparison(session, target.id)
    try:
        result = asyncio.run(run())
    except ServiceError as error:
        typer.echo(f"{error.code}: {error.message}", err=True)
        raise typer.Exit(1) from error
    output = {"run_id": result.id, "status": result.status, "metrics": result.metrics}
    case_count = result.dataset_manifest.get("test_count", "unknown")
    arm_count = len(result.requested_arms)
    typer.echo(
        json.dumps(output, sort_keys=True)
        if json_output
        else f"Run {result.id}: {result.status} ({case_count} cases × {arm_count} arms)"
    )


@cli.command("report")
def report_command(latest: bool = typer.Option(True, "--latest/--no-latest"), format: str = typer.Option("markdown"), json_output: bool = typer.Option(False, "--json")) -> None:
    """Render release evidence for the latest completed run."""
    async def run() -> Report:
        async with SessionLocal() as session:
            current = await session.scalar(
                select(Run)
                .join(Project, Run.project_id == Project.id)
                .where(
                    Project.workspace_id == LOCAL_WORKSPACE_ID,
                    Run.status == "succeeded",
                )
                .order_by(Run.finished_at.desc())
            )
            if not current:
                raise ServiceError("run_not_found", "No completed run is available.")
            return await create_report(session, current.id)
    try:
        report = asyncio.run(run())
    except ServiceError as error:
        typer.echo(f"{error.code}: {error.message}", err=True)
        raise typer.Exit(1) from error
    if format == "json" or json_output:
        typer.echo(json.dumps(report.evidence, sort_keys=True))
    else:
        typer.echo(report.rendered_markdown)


@cli.command("worker")
def worker_command(once: bool = typer.Option(False, help="Claim at most one queued job and exit.")) -> None:
    """Run the persisted SQL job worker."""
    from app.worker import run_worker
    asyncio.run(run_worker(once=once))


@cli.command("serve")
def serve_command() -> None:
    """Migrate under a PostgreSQL advisory lock, then replace this process with Uvicorn."""
    from app.deploy import exec_uvicorn, migrate_database

    migrate_database()
    exec_uvicorn()


@benchmark_cli.command("sync-tau-retail")
def sync_tau_retail() -> None:
    """Sync the pinned tau2-derived Retail-17 smoke-subset manifest."""
    from app.adapters.tau_sync import sync
    try:
        manifest = sync()
    except Exception as error:
        typer.echo(f"benchmark_sync_failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(manifest, indent=2, sort_keys=True))


@benchmark_cli.command("run-tau-retail")
def run_tau_retail(adapter: str = typer.Option("fixture")) -> None:
    """Validate availability of the imported Retail-17 smoke subset."""
    provenance = Path("../../data/benchmarks/tau3-retail/provenance.json")
    if not provenance.exists():
        typer.echo("benchmark_not_synced: run benchmark sync-tau-retail first", err=True)
        raise typer.Exit(1)
    typer.echo(f"Pinned dataset is available. Live tau execution remains optional; requested adapter={adapter}.")


if __name__ == "__main__":
    cli()
