"""Export versioned domain JSON Schemas and the FastAPI OpenAPI contract."""

import json
from pathlib import Path

from app.main import app
from app.schemas import (
    AllCondition,
    AnyCondition,
    BuildManifest,
    DatasetManifest,
    EvidencePayload,
    EvidenceReport,
    FactFixture,
    InputManifest,
    NotCondition,
    PolicyArtifact,
    PolicyDecisionRequest,
    PolicyDecisionResult,
    Predicate,
    RegressionArtifact,
    RuleException,
    RuleIR,
    RuleRequirement,
    RuleScope,
    RunManifest,
    SourceRef,
    TestCaseSpec,
    ToolRegistry,
    TraceEvent,
)

OUTPUT = Path(__file__).resolve().parents[1] / "schemas"
CONTRACTS = [
    SourceRef,
    Predicate,
    AllCondition,
    AnyCondition,
    NotCondition,
    RuleIR,
    PolicyDecisionRequest,
    PolicyDecisionResult,
    TestCaseSpec,
    TraceEvent,
    RunManifest,
    BuildManifest,
    InputManifest,
    DatasetManifest,
    PolicyArtifact,
    RegressionArtifact,
    ToolRegistry,
    FactFixture,
    RuleScope,
    RuleRequirement,
    RuleException,
    EvidencePayload,
    EvidenceReport,
]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for contract in CONTRACTS:
        path = OUTPUT / f"{contract.__name__}.schema.json"
        path.write_text(json.dumps(contract.model_json_schema(), indent=2, sort_keys=True) + "\n")
    openapi = Path(__file__).resolve().parents[1] / "openapi.json"
    openapi.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"Exported {len(CONTRACTS)} JSON Schemas and {openapi.name}.")


if __name__ == "__main__":
    main()
