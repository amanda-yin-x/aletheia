import { defineConfig, devices } from "@playwright/test";

const apiPort = Number(process.env.PLAYWRIGHT_API_PORT || "8000");
const webPort = Number(process.env.PLAYWRIGHT_WEB_PORT || "3000");
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://localhost:${webPort}`;
const isolatedNextOutput = process.env.PLAYWRIGHT_ISOLATED_WEB === "1"
  ? `NEXT_DIST_DIR=.next/playwright-${webPort} `
  : "";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: webOrigin, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command: `cd ../api && export ENVIRONMENT=local DATABASE_URL=sqlite+aiosqlite:///./.e2e.db MIGRATION_DATABASE_URL=sqlite:///./.e2e.db && uv run alembic upgrade head && uv run aletheia demo seed --reset && uv run uvicorn app.main:app --port ${apiPort}`,
      port: apiPort,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
    },
    {
      command: `AUTH_MODE=local SITE_URL=${webOrigin} API_ORIGIN_URL=${apiOrigin} ${isolatedNextOutput}PORT=${webPort} corepack pnpm dev`,
      port: webPort,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
