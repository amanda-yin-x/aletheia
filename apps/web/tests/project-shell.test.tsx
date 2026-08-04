import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectShell } from "@/components/project-shell";

const project = {
  id: "appointment-project",
  workspace_id: "workspace-1",
  slug: "appointment-scheduling",
  name: "Appointment Scheduling Agent",
  domain: "appointments",
  description: "A future fixture used only to verify shared-shell neutrality.",
  mode: "demo",
  created_at: "2026-08-03T00:00:00Z",
};

const mocks = vi.hoisted(() => ({
  pathname: "/projects/appointment-project/overview",
  api: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: mocks.api };
});

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  mocks.pathname = "/projects/appointment-project/overview";
  mocks.api.mockReset().mockResolvedValue(project);
});

afterEach(cleanup);

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ProjectShell projectId={project.id}><div>Appointment workspace content</div></ProjectShell>
    </QueryClientProvider>,
  );
}

describe("shared project shell", () => {
  it("renders a future domain from project data without Northstar or refund semantics", async () => {
    renderShell();

    expect(await screen.findByText("Appointment Scheduling Agent")).toBeInTheDocument();
    expect(screen.getByText("Appointments domain")).toBeInTheDocument();
    const rules = screen.getByRole("link", { name: "Rules" });
    expect(rules).toHaveAttribute("aria-label", "Rules");
    expect(rules).toHaveAttribute(
      "href",
      "/projects/appointment-project/rules",
    );
    expect(screen.getByRole("navigation", { name: "Project sections" })).toBeInTheDocument();
    expect(screen.queryByText(/Northstar/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/refund/i)).not.toBeInTheDocument();
  });

  it("exposes exactly one current destination on Overview", async () => {
    renderShell();
    await screen.findByText("Appointment Scheduling Agent");

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: "Report" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Report" })).not.toHaveClass("active");
  });

  it("uses the Report fragment as the sole current location when selected", async () => {
    window.history.replaceState(null, "", "/projects/appointment-project/overview#latest-report");
    renderShell();

    await waitFor(() => expect(screen.getByRole("link", { name: "Report" })).toHaveAttribute("aria-current", "location"));
    expect(screen.getByRole("link", { name: "Report" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveClass("active");
  });

  it("surfaces a project query failure and lets the user retry", async () => {
    mocks.api.mockRejectedValueOnce(new Error("The project API is unavailable."));
    renderShell();

    const alert = await screen.findByRole("alert", { name: "Project details error" });
    expect(alert).toHaveTextContent("Project details are unavailable.");
    expect(alert).toHaveTextContent("The project API is unavailable.");
    expect(screen.queryByText("Loading project context")).not.toBeInTheDocument();
    expect(screen.getByText("Appointment workspace content")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry project details" }));
    expect(await screen.findByText("Appointment Scheduling Agent")).toBeInTheDocument();
    expect(screen.queryByRole("alert", { name: "Project details error" })).not.toBeInTheDocument();
  });
});
