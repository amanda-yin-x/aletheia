from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

REPOSITORY = "https://github.com/sierra-research/tau2-bench"
TAG = "v1.0.1"
EXPECTED_SHORT_COMMIT = "fc0055d"
TASK_IDS = [10, 11, 12, 13, 16, 24, 30, 31, 48, 50, 51, 53, 57, 76, 82, 83, 84]
# Keep the checked-in storage path stable; public labels identify the upstream
# tau2 source and the bounded Aletheia Retail-17 selection accurately.
OUTPUT = get_settings().data_root / "benchmarks" / "tau3-retail"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_retail_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize only the reviewed manifest into an adapter-neutral import contract."""
    by_id = {int(task["id"]): task for task in tasks}
    missing = [task_id for task_id in TASK_IDS if task_id not in by_id]
    if missing:
        raise RuntimeError(f"Pinned Retail data is missing manifest tasks: {missing}")
    normalized = []
    for task_id in TASK_IDS:
        task = by_id[task_id]
        instructions = (task.get("user_scenario") or {}).get("instructions") or {}
        criteria = task.get("evaluation_criteria") or {}
        normalized.append(
            {
                "id": f"retail17.{task_id}",
                "upstream_task_id": str(task_id),
                "title": f"Retail-17 task {task_id}",
                "purpose": instructions.get("reason_for_call") or "Upstream Retail policy task",
                "provenance": {
                    "source": "tau2-retail-v1.0.1",
                    "upstream_path": "data/tau2/domains/retail/tasks.json",
                    "selector": f"id={task_id}",
                },
                "messages": [
                    {
                        "role": "user",
                        "content": instructions.get("reason_for_call") or "See upstream task instructions.",
                    }
                ],
                "initial_state": task.get("initial_state"),
                "expected": {
                    "actions": criteria.get("actions", []),
                    "communicate_info": criteria.get("communicate_info", []),
                },
                "source_record": task,
            }
        )
    return {
        "schema_version": "0.1",
        "label": "Simulated, real-world-like retail benchmark—not real customer data.",
        "task_count": len(normalized),
        "task_ids": TASK_IDS,
        "tasks": normalized,
    }


def sync() -> dict[str, Any]:
    """Fetch and provenance-check the pinned Retail benchmark without modifying upstream."""
    with tempfile.TemporaryDirectory(prefix="aletheia-retail17-") as temp:
        checkout = Path(temp) / "tau2-bench"
        subprocess.run(["git", "clone", "--depth", "1", "--branch", TAG, REPOSITORY, str(checkout)], check=True, capture_output=True, text=True)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, check=True, capture_output=True, text=True).stdout.strip()
        if not commit.startswith(EXPECTED_SHORT_COMMIT):
            raise RuntimeError(f"Pinned tag resolved to {commit[:7]}, expected {EXPECTED_SHORT_COMMIT}")
        candidates = [
            "data/tau2/domains/retail/policy.md",
            "data/tau2/domains/retail/db.json",
            "data/tau2/domains/retail/tasks.json",
            "data/tau2/domains/retail/split_tasks.json",
        ]
        selected: dict[str, str] = {}
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for relative in candidates:
            source = checkout / relative
            if not source.exists():
                raise RuntimeError(f"Pinned upstream path is missing: {relative}")
            target = OUTPUT / source.name
            shutil.copy2(source, target)
            selected[relative] = _sha(target)
        raw_tasks = json.loads((OUTPUT / "tasks.json").read_text(encoding="utf-8"))
        normalized = normalize_retail_tasks(raw_tasks)
        normalized_path = OUTPUT / "selected-tasks.json"
        normalized_path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        selected["normalized/selected-tasks.json"] = _sha(normalized_path)
        license_source = checkout / "LICENSE"
        if license_source.exists():
            shutil.copy2(license_source, OUTPUT / "LICENSE.upstream")
            selected["LICENSE"] = _sha(OUTPUT / "LICENSE.upstream")
        manifest = {
            "schema_version": "0.1",
            "label": "Simulated, real-world-like retail benchmark—not real customer data.",
            "repository": REPOSITORY,
            "tag": TAG,
            "commit": commit,
            "task_ids": TASK_IDS,
            "task_manifest": [
                {
                    "task_id": item["upstream_task_id"],
                    "purpose": item["purpose"],
                    "upstream_path": item["provenance"]["upstream_path"],
                }
                for item in normalized["tasks"]
            ],
            "excluded_known_open_tasks": [4, 5, 7],
            "selected_file_hashes": selected,
            "imported_at": datetime.now(UTC).isoformat(),
            "license": "MIT; copyright Sierra Research 2025",
        }
        (OUTPUT / "provenance.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
