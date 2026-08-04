import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const UPDATE_DOC_SCREENSHOTS = process.env.UPDATE_DOC_SCREENSHOTS === "1";

async function captureDocumentationScreenshot(page: Page, name: string) {
  if (!UPDATE_DOC_SCREENSHOTS) return;
  await page.screenshot({ path: `../../docs/screenshots/${name}.png`, animations: "disabled" });
}

async function reset(request: APIRequestContext) {
  const response = await request.post(`${API}/api/v1/demo/reset`);
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{ id: string }>;
}

async function resolveAndApprove(request: APIRequestContext) {
  const project = await reset(request);
  const rules = await (await request.get(`${API}/api/v1/projects/${project.id}/rules`)).json() as Array<{ id: string; stable_key: string; revision: number }>;
  const findings = await (await request.get(`${API}/api/v1/projects/${project.id}/findings`)).json() as Array<{ id: string; severity: string; related_rule_ids: string[] }>;
  for (const finding of findings.filter((item) => item.severity === "critical")) {
    const related = rules.filter((rule) => finding.related_rule_ids.includes(rule.id));
    const winner = related.find((rule) => !rule.stable_key.startsWith("rule.legacy."))!;
    const loser = related.find((rule) => rule.stable_key.startsWith("rule.legacy."))!;
    const response = await request.patch(`${API}/api/v1/findings/${finding.id}`, { data: { resolution_state: "resolved", expected_resolution_state: "open", winner_rule_id: winner.id, loser_rule_id: loser.id, authority: "Refund Policy v3 is current.", resolution_note: "Current policy v3 selected in E2E review." } });
    expect(response.ok()).toBeTruthy();
  }
  const refreshedRules = await (await request.get(`${API}/api/v1/projects/${project.id}/rules`)).json() as Array<{ id: string; stable_key: string; revision: number }>;
  const threshold = refreshedRules.find((item) => item.stable_key === "rule.refund.approval_threshold")!;
  const approval = await request.post(`${API}/api/v1/rules/${threshold.id}/approve`, { data: { expected_revision: threshold.revision } });
  expect(approval.ok()).toBeTruthy();
  return project;
}

test("landing opens the workspace and shows the composite refund failure", async ({ page, request }) => {
  await reset(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "The policy CI for AI agents." })).toBeVisible();
  const typedDecision = page.locator(".typed-decision-text");
  await expect(typedDecision).toHaveText("decision = deny");
  await expect.poll(() => typedDecision.evaluate((element) => element.getAnimations()[0]?.playState)).toBe("finished");
  await captureDocumentationScreenshot(page, "landing-desktop");
  await expect(page.getByText("The agent’s plan looks valid. The action is not.")).toBeVisible();
  await expect(page.getByText("N-1099 · day 9 · $249")).toBeVisible();
  if (UPDATE_DOC_SCREENSHOTS) {
    await page.locator("#why").screenshot({ path: "../../docs/screenshots/composite-refund-desktop.png", animations: "disabled" });
  }
  await page.getByRole("tab", { name: "Without a gate" }).click();
  await expect(page.getByText("A plausible plan becomes a forbidden mutation.")).toBeVisible();
  await page.getByRole("tab", { name: "With Aletheia" }).click();
  await expect(page.getByText("The current policy stops the mutation.")).toBeVisible();
  await page.getByRole("tab", { name: "With Aletheia" }).focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Without a gate" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("A plausible plan becomes a forbidden mutation.")).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "With Aletheia" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("link", { name: /Inspect the refund decision/ }).click();
  await expect(page).toHaveURL(/\/projects\/[^/]+\/overview$/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Northstar Retail Refund Agent" })).toBeVisible();
  await page.getByRole("link", { name: "Rules" }).click();
  await expect(page.getByText("Conflict: current policy says 30 days; the legacy SOP says 60 days.")).toBeVisible();
  await page.getByRole("link", { name: "Sources" }).click();
  await expect(page.getByRole("region", { name: /Numbered source/ })).toBeVisible();
  await page.getByRole("button", { name: /refund-sop-legacy.md/ }).click();
  await expect(page.getByText("Agents may approve returns received within 60 calendar days of delivery.")).toBeVisible();
  await page.setViewportSize({ width: 820, height: 1024 });
  await captureDocumentationScreenshot(page, "sources-tablet");
});

test("landing command palette and reduced-motion mode remain usable", async ({ page, request }) => {
  await reset(request);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const intro = page.locator(".marketing-intro").first();
  await expect(intro).toHaveCSS("opacity", "1");
  await expect(intro).toHaveCSS("transform", "none");
  await expect(page.locator(".typed-decision-visual")).toHaveText("decision = deny");
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
    await expect(page.getByRole("heading", { name: "The policy CI for AI agents." })).toBeVisible();
    await expect(page.getByRole("link", { name: /Inspect the refund decision/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open jump menu" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
  }
});

test("review resolves conflicts, approves the threshold, and builds a measured candidate", async ({ page, request }) => {
  const project = await reset(request);
  await page.goto(`/projects/${project.id}/rules`);
  for (const rationale of [
    "The current policy revision sets the release window; the legacy SOP is superseded.",
    "The current policy revision sets the approval boundary; the legacy SOP is superseded.",
  ]) {
    await page.getByRole("button", { name: "Review conflict" }).first().click();
    const decision = page.getByRole("form", { name: /Resolve conflict:/ });
    await decision.getByRole("radio", { name: /refund-policy-v3\.md/i }).click();
    await decision.getByLabel("Decision authority").fill("Refund Policy v3, approved by Policy Operations");
    await decision.getByLabel("Resolution rationale").fill(rationale);
    await decision.getByRole("button", { name: "Save resolution" }).click();
    await expect(decision).toBeHidden();
  }
  await expect(page.getByRole("button", { name: "Review conflict" })).toHaveCount(0);
  await page.getByText("Approval above $200", { exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("tool.arguments.amount");
  await page.getByRole("button", { name: "Approve revision" }).click();
  await expect(page.getByRole("dialog").getByText("Approved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close rule details" }).click();
  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("button", { name: "Build candidate" }).click();
  await expect(page.getByText("Original / prompt kernel")).toBeVisible();
  await expect(page.getByText("char_4_estimate")).toBeVisible();
  await expect(page.getByText("Stored", { exact: true })).toBeVisible();
  await captureDocumentationScreenshot(page, "build-desktop");
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
  await captureDocumentationScreenshot(page, "guarded-trace-desktop");
  await page.getByRole("link", { name: "Back to run comparison" }).click();
  await page.getByRole("button", { name: "Create evidence report" }).click();
  await expect(page.getByRole("heading", { name: "Scope and evidence boundary" })).toBeVisible();
  const download = page.getByRole("link", { name: "Download Markdown" });
  await expect(download).toHaveAttribute("href", /format=markdown/);
  await captureDocumentationScreenshot(page, "report-desktop");
});
