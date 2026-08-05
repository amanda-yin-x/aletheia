"""Public compiler service facade.

The implementation lives in the domain-neutral compilation package.  Keeping
this module preserves the stable service import used by the API, worker, CLI,
runner, and existing integrations.
"""

from app.services.compilation.bundle import (
    COMPILER_VERSION,
    EVIDENCE_LIMIT,
    FACT_ARTIFACT,
    POLICY_ARTIFACT,
    ROOT_ARTIFACT,
    RUNNER_INPUT_VERSION,
    TEST_ARTIFACT,
    TOOL_ARTIFACT,
    compile_project,
)

__all__ = [
    "COMPILER_VERSION",
    "EVIDENCE_LIMIT",
    "FACT_ARTIFACT",
    "POLICY_ARTIFACT",
    "ROOT_ARTIFACT",
    "RUNNER_INPUT_VERSION",
    "TEST_ARTIFACT",
    "TOOL_ARTIFACT",
    "compile_project",
]
