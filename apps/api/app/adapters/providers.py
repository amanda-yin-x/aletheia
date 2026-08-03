from __future__ import annotations

from typing import Any, Protocol

from app.services.errors import ServiceError


class RuleExtractor(Protocol):
    async def extract(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class AgentAdapter(Protocol):
    async def trajectory(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


class FixtureExtractor:
    """Return checked-in candidates; application code still verifies exact quotes."""

    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self.candidates = candidates

    async def extract(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        del chunks
        return self.candidates


class StructuredLLMExtractor:
    """Optional structured-output seam with no tools and no silent fallback."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def extract(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        del chunks
        if not self.api_key:
            raise ServiceError(
                "live_extractor_not_configured",
                "Set a server-side model key before selecting structured extraction. Fixture extraction remains available.",
                status_code=503,
            )
        raise ServiceError(
            "live_extractor_dependency_missing",
            "Install the optional live dependency group to use structured extraction.",
            status_code=503,
        )


class OpenAICompatibleAgentAdapter:
    """Optional live tool-loop seam; never imported or called by fixture tests."""

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def trajectory(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        del request
        if not self.api_key:
            raise ServiceError(
                "live_agent_not_configured",
                "Set a server-side model key before selecting a live agent. Fixture runs remain available.",
                status_code=503,
            )
        raise ServiceError(
            "live_agent_dependency_missing",
            "Install the optional live dependency group to run a provider tool loop.",
            status_code=503,
        )
