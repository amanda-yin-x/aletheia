import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/appointment-project/overview",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: vi.fn(async () => project) };
});

describe("shared project shell", () => {
  it("renders a future domain from project data without Northstar or refund semantics", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ProjectShell projectId={project.id}><div>Appointment workspace content</div></ProjectShell>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Appointment Scheduling Agent")).toBeInTheDocument();
    expect(screen.getByText("Appointments domain")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Rules" })).toHaveAttribute(
      "href",
      "/projects/appointment-project/rules",
    );
    expect(screen.queryByText(/Northstar/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/refund/i)).not.toBeInTheDocument();
  });
});
