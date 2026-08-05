from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.services.appointment_seed import seed_appointment_demo
from app.services.errors import ServiceError
from app.services.seed import seed_demo

FixtureSeeder = Callable[..., Awaitable[Project]]


@dataclass(frozen=True)
class DemoFixture:
    slug: str
    seed: FixtureSeeder
    primary: bool = False


DEMO_FIXTURES = (
    DemoFixture(slug="northstar-retail", seed=seed_demo, primary=True),
    DemoFixture(slug="acme-appointments", seed=seed_appointment_demo),
)
FIXTURES_BY_SLUG = {fixture.slug: fixture for fixture in DEMO_FIXTURES}


def demo_fixture_slugs() -> tuple[str, ...]:
    return tuple(sorted(FIXTURES_BY_SLUG))


def primary_fixture(projects: list[Project]) -> Project:
    primary_slug = next(fixture.slug for fixture in DEMO_FIXTURES if fixture.primary)
    return next(project for project in projects if project.slug == primary_slug)


async def seed_workspace_fixtures(
    session: AsyncSession,
    *,
    workspace_id: str | None = None,
    reset: bool = False,
) -> list[Project]:
    projects: list[Project] = []
    selected_workspace = workspace_id
    for fixture in DEMO_FIXTURES:
        project = await fixture.seed(
            session,
            workspace_id=selected_workspace,
            reset=reset,
        )
        selected_workspace = project.workspace_id
        projects.append(project)
    return projects


async def reset_fixture_project(session: AsyncSession, project: Project) -> Project:
    fixture = FIXTURES_BY_SLUG.get(project.slug)
    if fixture is None:
        raise ServiceError("project_not_found", "Project not found.", status_code=404)
    return await fixture.seed(
        session,
        workspace_id=project.workspace_id,
        reset=True,
    )
