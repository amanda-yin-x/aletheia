import os
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# The application defaults to fail-closed production mode. Tests opt into the
# fixed test identity before importing any module that constructs Settings.
os.environ.setdefault("ENVIRONMENT", "test")

from app.db import Base  # noqa: E402
from app.services.seed import seed_demo  # noqa: E402


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as value:
        await seed_demo(value)
        yield value
    await engine.dispose()
