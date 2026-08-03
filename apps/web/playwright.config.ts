import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: "cd ../api && uv run uvicorn app.main:app --port 8000", port: 8000, reuseExistingServer: !process.env.CI },
    { command: "corepack pnpm dev", port: 3000, reuseExistingServer: !process.env.CI },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
