import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SiteHeader } from "@/components/site-header";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  fetch: vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/project-1/overview",
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh, push: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({
  api: vi.fn(async () => ({ id: "guest-1", email: null, is_anonymous: true, workspaces: [{ id: "workspace-1", name: "My workspace", role: "owner" }] })),
  ensureCsrfToken: vi.fn(async () => "csrf-token"),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("account menu", () => {
  it("labels anonymous workspace sessions as Guest demo", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SiteHeader /></QueryClientProvider>);
    expect((await screen.findAllByText("Guest demo")).length).toBeGreaterThan(0);
    expect(screen.getByText("Temporary guest session")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Keep this workspace" })).toHaveAttribute(
      "href",
      "/login?next=%2Fprojects%2Fproject-1%2Foverview",
    );
    expect(screen.getByRole("button", { name: "End guest session" })).toBeInTheDocument();
  });

  it("returns a guest to the public landing page when the session ends", async () => {
    vi.stubGlobal("fetch", mocks.fetch);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SiteHeader /></QueryClientProvider>);

    fireEvent.click(await screen.findByRole("button", { name: "End guest session" }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/"));
    expect(mocks.refresh).toHaveBeenCalled();
  });
});
