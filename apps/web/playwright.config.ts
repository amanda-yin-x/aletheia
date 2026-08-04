import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command: "cd ../api && export ENVIRONMENT=local DATABASE_URL=sqlite+aiosqlite:///./.e2e.db MIGRATION_DATABASE_URL=sqlite:///./.e2e.db && uv run alembic upgrade head && uv run aletheia demo seed --reset && uv run uvicorn app.main:app --port 8000",
      port: 8000,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
    },
    {
      command: "AUTH_MODE=local SITE_URL=http://localhost:3000 API_ORIGIN_URL=http://127.0.0.1:8000 corepack pnpm dev",
      port: 3000,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
