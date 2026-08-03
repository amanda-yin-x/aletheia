#!/usr/bin/env python3
"""CLI wrapper for the provenance-checking tau3 Retail sync adapter."""

import json
from pathlib import Path


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
    from app.adapters.tau_sync import sync

    print(json.dumps(sync(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
