import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT || "8000"}`;
const UPDATE_DOC_SCREENSHOTS = process.env.UPDATE_DOC_SCREENSHOTS === "1";

interface ProjectRecord {
  id: string;
  slug: string;
  name: string;
  domain: string;
}

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

async function projectList(request: APIRequestContext): Promise<ProjectRecord[]> {
  const response = await request.get(`${API}/api/v1/projects`);
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<ProjectRecord[]>;
}

async function resolveProjectConflicts(request: APIRequestContext, projectId: string) {
  const rulesResponse = await request.get(`${API}/api/v1/projects/${projectId}/rules`);
  const findingsResponse = await request.get(`${API}/api/v1/projects/${projectId}/findings`);
  expect(rulesResponse.ok()).toBeTruthy();
  expect(findingsResponse.ok()).toBeTruthy();
  const rules = await rulesResponse.json() as Array<{ id: string; stable_key: string }>;
  const findings = await findingsResponse.json() as Array<{ id: string; severity: string; resolution_state: string; related_rule_ids: string[] }>;
  for (const finding of findings.filter((item) => item.severity === "critical" && item.resolution_state === "open")) {
    const related = rules.filter((rule) => finding.related_rule_ids.includes(rule.id));
    const winner = related.find((rule) => !rule.stable_key.includes("legacy"));
    const loser = related.find((rule) => rule.stable_key.includes("legacy"));
    expect(winner, "a current authority rule is required").toBeTruthy();
    expect(loser, "a legacy authority rule is required").toBeTruthy();
    const response = await request.patch(`${API}/api/v1/findings/${finding.id}`, {
      data: {
        resolution_state: "resolved",
        expected_resolution_state: "open",
        winner_rule_id: winner!.id,
        loser_rule_id: loser!.id,
        authority: "Current project policy is authoritative.",
        resolution_note: "Current authority selected in the two-domain browser review.",
      },
    });
    expect(response.ok()).toBeTruthy();
  }
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
  await expect(page.getByRole("navigation", { name: "Compiled bundle tree" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Compilation metrics" })).toBeVisible();
  await expect(page.getByText("char_div_4 · 1.0.0")).toBeVisible();
  await expect(page.getByText("Behavioral fidelity: Not measured")).toBeVisible();
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

test("two domains keep project routing and compiled evidence isolated", async ({ page, request }) => {
  test.setTimeout(60_000);
  const northstar = await resolveAndApprove(request);
  const projects = await projectList(request);
  const acme = projects.find((project) => project.slug === "acme-appointments");
  expect(acme, "the Acme appointment project must be seeded").toBeTruthy();
  expect(projects.some((project) => project.id === northstar.id)).toBeTruthy();
  await resolveProjectConflicts(request, acme!.id);

  await page.goto(`/projects/${northstar.id}/overview`);
  const selector = page.getByRole("combobox", { name: "Project / domain" });
  await expect(selector).toBeEnabled({ timeout: 15_000 });
  await expect(selector).toHaveValue(northstar.id, { timeout: 15_000 });
  await expect(selector.locator("option")).toHaveCount(2);
  await selector.selectOption(acme!.id);
  await expect(page).toHaveURL(`/projects/${acme!.id}/overview`);
  await expect(page.getByRole("heading", { name: "Acme Appointment Scheduling Agent" })).toBeVisible();

  await page.getByRole("link", { name: "Placements" }).click();
  await expect(page.getByRole("heading", { name: "Placements" })).toBeVisible();
  const identityPlacement = page.locator("article.placement-card").filter({ hasText: "Verify identity before appointment change" });
  await expect(identityPlacement).toContainText("Pre-tool guard");
  await expect(identityPlacement).toContainText("Current");
  const pendingPlacement = page.locator("article.placement-card").filter({ hasText: "Maximum completed reschedules" });
  await expect(pendingPlacement).toContainText("Blocked");
  await expect(pendingPlacement).toContainText("Human review");
  const unsupportedPlacement = page.locator("article.placement-card").filter({ hasText: "Undefined daylight-hours preference" });
  await expect(unsupportedPlacement).toContainText("Unsupported");
  await page.getByRole("heading", { name: "Placements" }).scrollIntoViewIfNeeded();
  await captureDocumentationScreenshot(page, "acme-routing-desktop");

  await page.getByRole("link", { name: "Build" }).click();
  await page.getByRole("button", { name: /Build (candidate|new snapshot)/ }).click();
  await expect(page.getByRole("navigation", { name: "Compiled bundle tree" })).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(new RegExp(`/projects/${acme!.id}/builds/[^/]+$`));
  await expect(page.getByRole("button", { name: "prompt-kernel.md" })).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("heading", { name: "Compilation metrics" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Routing report" })).toBeVisible();
  const routingPanel = page.locator("section.routing-report-panel");
  await expect(routingPanel).not.toContainText("Routing report unavailable");
  await expect(routingPanel).toContainText("Verify identity before appointment change");
  await expect(page.getByRole("heading", { name: "Preservation report" })).toBeVisible();
  await expect(page.getByText("Behavioral fidelity: Not measured")).toBeVisible();
  const mappedRule = page.getByRole("button", { name: /rule\.appointment\.style@1/ }).first();
  await mappedRule.click();
  await expect(page.getByText("Exact source anchors")).toBeVisible();
  await expect(page.getByRole("link", { name: /Open exact source/ }).first()).toHaveAttribute("href", new RegExp(`/projects/${acme!.id}/sources\\?document=.+#line-`));
  await page.locator(".artifact-provenance").scrollIntoViewIfNeeded();
  await captureDocumentationScreenshot(page, "acme-build-desktop");

  const buildSelector = page.getByRole("combobox", { name: "Project / domain" });
  await expect(buildSelector).toHaveValue(acme!.id, { timeout: 15_000 });
  await buildSelector.selectOption(northstar.id);
  await expect(page).toHaveURL(`/projects/${northstar.id}/overview`);
  await expect(page.getByRole("combobox", { name: "Project / domain" })).toHaveValue(northstar.id, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Northstar Retail Refund Agent" })).toBeVisible();
  await page.getByRole("link", { name: "Placements" }).click();
  await expect(page).toHaveURL(`/projects/${northstar.id}/routing`);
  await expect(page.getByRole("heading", { name: "Placements" })).toBeVisible();
  await expect(page.getByText("Approval above $200", { exact: true })).toBeVisible();
  await expect(page.getByText("Verify identity before appointment change", { exact: true })).toHaveCount(0);
});
