SHELL := /bin/bash

.PHONY: bootstrap demo test ci api web benchmark-sync migration-check audit

bootstrap:
	cd apps/api && uv sync --all-groups
	corepack pnpm install --frozen-lockfile
	cd apps/api && ENVIRONMENT=local uv run alembic upgrade head
	cd apps/api && ENVIRONMENT=local uv run aletheia demo seed --reset
	cd apps/api && ENVIRONMENT=local uv run python scripts/export_contracts.py
	corepack pnpm --filter @aletheia/web exec openapi-typescript ../../apps/api/openapi.json -o ../../packages/api-client/src/schema.d.ts

demo:
	@echo "Aletheia API: http://localhost:8000"
	@echo "Aletheia web: http://localhost:3000"
	@trap 'kill 0' EXIT; (cd apps/api && ENVIRONMENT=local uv run uvicorn app.main:app --reload --port 8000) & corepack pnpm --filter @aletheia/web dev

api:
	cd apps/api && ENVIRONMENT=local uv run uvicorn app.main:app --reload --port 8000

web:
	corepack pnpm --filter @aletheia/web dev

test:
	cd apps/api && ENVIRONMENT=test uv run pytest
	cd apps/api && ENVIRONMENT=test uv run python scripts/export_contracts.py
	corepack pnpm --filter @aletheia/web exec openapi-typescript ../../apps/api/openapi.json -o ../../packages/api-client/src/schema.d.ts
	corepack pnpm --filter @aletheia/web test

migration-check:
	@task_tmp=$$(mktemp -d); trap 'rm -rf "$$task_tmp"' EXIT; \
		cd apps/api && \
		ENVIRONMENT=test \
		DATABASE_URL="sqlite+aiosqlite:///$$task_tmp/aletheia.db" \
		MIGRATION_DATABASE_URL="sqlite:///$$task_tmp/aletheia.db" \
		uv run alembic upgrade head && \
		ENVIRONMENT=test \
		DATABASE_URL="sqlite+aiosqlite:///$$task_tmp/aletheia.db" \
		MIGRATION_DATABASE_URL="sqlite:///$$task_tmp/aletheia.db" \
		uv run alembic check

audit:
	cd apps/api && uv run pip-audit
	corepack pnpm audit --prod --audit-level high

ci:
	$(MAKE) audit
	cd apps/api && uv run ruff check app tests
	cd apps/api && uv run mypy app
	cd apps/api && ENVIRONMENT=test uv run pytest
	$(MAKE) migration-check
	cd apps/api && ENVIRONMENT=test uv run python scripts/export_contracts.py
	corepack pnpm --filter @aletheia/web exec openapi-typescript ../../apps/api/openapi.json -o ../../packages/api-client/src/schema.d.ts
	git diff --exit-code -- apps/api/openapi.json apps/api/schemas packages/api-client/src/schema.d.ts
	corepack pnpm --filter @aletheia/web lint
	corepack pnpm --filter @aletheia/web run cf-typegen
	corepack pnpm --filter @aletheia/web typecheck
	corepack pnpm --filter @aletheia/web test
	corepack pnpm --filter @aletheia/web exec opennextjs-cloudflare build
	corepack pnpm --filter @aletheia/web exec wrangler deploy --dry-run --env=""
	corepack pnpm --filter @aletheia/web exec wrangler deploy --dry-run --env staging

benchmark-sync:
	cd apps/api && ENVIRONMENT=local uv run aletheia benchmark sync-tau-retail
