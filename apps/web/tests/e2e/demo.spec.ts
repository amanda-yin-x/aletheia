import { expect, test, type APIRequestContext } from "@playwright/test";

const API = "http://127.0.0.1:8000";

async function reset(request: APIRequestContext) {
  const response = await request.post(`${API}/api/v1/demo/reset`);
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{ id: string }>;
}

async function resolveAndApprove(request: APIRequestContext) {
  const project = await reset(request);
  const findings = await (await request.get(`${API}/api/v1/projects/${project.id}/findings`)).json() as Array<{ id: string; severity: string }>;
  for (const finding of findings.filter((item) => item.severity === "critical")) {
    const response = await request.patch(`${API}/api/v1/findings/${finding.id}`, { data: { resolution_state: "resolved", resolution_note: "Current policy v3 selected in E2E review." } });
    expect(response.ok()).toBeTruthy();
  }
  const rules = await (await request.get(`${API}/api/v1/projects/${project.id}/rules`)).json() as Array<{ id: string; stable_key: string; revision: number }>;
  const threshold = rules.find((item) => item.stable_key === "rule.refund.approval_threshold")!;
  const approval = await request.post(`${API}/api/v1/rules/${threshold.id}/approve`, { data: { expected_revision: threshold.revision } });
  expect(approval.ok()).toBeTruthy();
  return project;
}

test("landing opens the demo and shows the source-linked 30/60-day conflict", async ({ page, request }) => {
  await reset(request);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Catch policy drift before your agent acts." })).toBeVisible();
  await expect(page.getByText("One refund. Three documents. Two answers.")).toBeVisible();
  await page.getByRole("tab", { name: "Without a gate" }).click();
  await expect(page.getByText("The fixture executes the call.")).toBeVisible();
  await page.getByRole("tab", { name: "With Aletheia" }).click();
  await expect(page.getByText("The guard intercepts before execution.")).toBeVisible();
  await page.getByRole("tab", { name: "With Aletheia" }).focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Without a gate" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("The fixture executes the call.")).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "With Aletheia" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("link", { name: /Run the refund scenario/ }).click();
  await expect(page.getByRole("heading", { name: "Northstar Retail Refund Agent" })).toBeVisible();
  await page.getByRole("link", { name: "Rules" }).click();
  await expect(page.getByText("Conflict: current policy says 30 days; the legacy SOP says 60 days.")).toBeVisible();
  await page.getByRole("link", { name: "Sources" }).click();
  await expect(page.getByRole("region", { name: /Numbered source/ })).toBeVisible();
  await page.getByRole("button", { name: /refund-sop-legacy.md/ }).click();
  await expect(page.getByText("Agents may approve returns received within 60 calendar days of delivery.")).toBeVisible();
});

test("landing command palette and reduced-motion mode remain usable", async ({ page, request }) => {
  await reset(request);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const intro = page.locator(".marketing-intro").first();
  await expect(intro).toHaveCSS("opacity", "1");
  await expect(intro).toHaveCSS("transform", "none");
  await expect(page.locator(".typed-decision-visual")).toHaveText("decision = require_approval");
  await page.keyboard.press("Control+K");
  const dialog = page.getByRole("dialog", { name: "Jump to a page or section" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("combobox", { name: "Search destinations" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close jump menu" })).toBeVisible();
  await dialog.getByRole("combobox", { name: "Search destinations" }).fill("roadmap");
  await expect(dialog.getByRole("option", { name: /Read the production roadmap/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.keyboard.press("Control+K");
  await dialog.getByRole("combobox", { name: "Search destinations" }).fill("produces");
  await dialog.getByRole("option", { name: /What the build produces/ }).click();
  const evidenceTop = await page.getByRole("heading", { name: "A reviewed change leaves artifacts—not vibes." }).evaluate((element) => element.getBoundingClientRect().top);
  expect(evidenceTop).toBeGreaterThanOrEqual(68);
});

test("landing has no horizontal overflow at supported narrow widths", async ({ page, request }) => {
  await reset(request);
  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Catch policy drift before your agent acts." })).toBeVisible();
    await expect(page.getByRole("link", { name: /Run the refund scenario/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open jump menu" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
  }
});

test("review resolves conflicts, approves the threshold, and builds a measured candidate", async ({ page, request }) => {
  const project = await reset(request);
  await page.goto(`/projects/${project.id}/rules`);
  const useCurrent = page.getByRole("button", { name: "Use current policy" });
  await useCurrent.first().click();
  await expect(useCurrent).toHaveCount(1);
  await useCurrent.first().click();
  await expect(useCurrent).toHaveCount(0);
  await page.getByText("Approval above $200", { exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("tool.arguments.amount");
  await page.getByRole("button", { name: "Approve revision" }).click();
  await expect(page.getByRole("dialog").getByText("Approved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close rule details" }).click();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("button", { name: "Build candidate" }).click();
  await expect(page.getByText("Original / prompt kernel")).toBeVisible();
  await expect(page.getByText("char_4_estimate")).toBeVisible();
  await expect(page.getByText("Immutable", { exact: true })).toBeVisible();
});

test("run comparison exposes the blocked $200.01 trace and exports evidence", async ({ page, request }) => {
  const project = await resolveAndApprove(request);
  const buildResponse = await request.post(`${API}/api/v1/projects/${project.id}/builds`, { data: {} });
  expect(buildResponse.ok()).toBeTruthy();
  await page.goto(`/projects/${project.id}/tests`);
  await page.getByRole("button", { name: "Run comparison" }).click();
  await expect(page.getByRole("heading", { name: "Release behavior" })).toBeVisible();
  const boundaryRow = page.getByRole("row").filter({ hasText: "$200.01 without approval routes for approval" });
  await boundaryRow.getByRole("link", { name: "Inspect trace" }).click();
  await expect(page.getByRole("heading", { name: "$200.01 without approval routes for approval" })).toBeVisible();
  await expect(page.getByText("Proposal intercepted; approval route returned; state not mutated.")).toBeVisible();
  await expect(page.getByText("Proposed", { exact: true })).toBeVisible();
  await expect(page.getByText("Executed", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Back to run comparison" }).click();
  await page.getByRole("button", { name: "Create evidence report" }).click();
  await expect(page.getByRole("heading", { name: "Scope and evidence boundary" })).toBeVisible();
  const download = page.getByRole("link", { name: "Download Markdown" });
  await expect(download).toHaveAttribute("href", /format=markdown/);
});
