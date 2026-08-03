SHELL := /bin/bash

.PHONY: bootstrap demo test ci api web benchmark-sync

bootstrap:
	cd apps/api && uv sync --all-groups
	corepack pnpm install --frozen-lockfile
	cd apps/api && uv run alembic upgrade head
	cd apps/api && uv run aletheia demo seed --reset
	cd apps/api && uv run python scripts/export_contracts.py
	corepack pnpm --filter @aletheia/web exec openapi-typescript ../../apps/api/openapi.json -o ../../packages/api-client/src/schema.d.ts

demo:
	@echo "Aletheia API: http://localhost:8000"
	@echo "Aletheia web: http://localhost:3000"
	@trap 'kill 0' EXIT; (cd apps/api && uv run uvicorn app.main:app --reload --port 8000) & corepack pnpm --filter @aletheia/web dev

api:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

web:
	corepack pnpm --filter @aletheia/web dev

test:
	cd apps/api && uv run pytest
	cd apps/api && uv run python scripts/export_contracts.py
	corepack pnpm --filter @aletheia/web exec openapi-typescript ../../apps/api/openapi.json -o ../../packages/api-client/src/schema.d.ts
	corepack pnpm --filter @aletheia/web test

ci:
	cd apps/api && uv run ruff check app tests
	cd apps/api && uv run mypy app
	cd apps/api && uv run pytest
	corepack pnpm --filter @aletheia/web lint
	corepack pnpm --filter @aletheia/web typecheck
	corepack pnpm --filter @aletheia/web test
	corepack pnpm --filter @aletheia/web exec wrangler types --env-interface CloudflareEnv --include-runtime false --check cloudflare-env.d.ts
	corepack pnpm --filter @aletheia/web exec opennextjs-cloudflare build
	corepack pnpm --filter @aletheia/web exec wrangler deploy --dry-run

benchmark-sync:
	cd apps/api && uv run aletheia benchmark sync-tau-retail
