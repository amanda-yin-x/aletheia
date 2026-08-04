import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoEntry } from "@/components/demo-entry";

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  replace: vi.fn(),
  signInAnonymously: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: mocks.api };
});
vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({ auth: { signInAnonymously: mocks.signInAnonymously } }),
}));
vi.mock("@/components/turnstile-widget", () => ({
  TurnstileWidget: ({ action, onToken }: { action: string; onToken: (token: string) => void }) => (
    <button type="button" data-action={action} onClick={() => onToken("guest-captcha")}>Complete guest verification</button>
  ),
}));

const config = {
  url: "https://project.supabase.co",
  publishableKey: "publishable",
  turnstileSiteKey: "site-key",
  siteUrl: "https://aletheia.example",
  githubAuthEnabled: true,
  emailOtpEnabled: true,
};

function renderEntry(initialHasSession: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><DemoEntry config={config} initialHasSession={initialHasSession} /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.signInAnonymously.mockResolvedValue({ data: { session: { access_token: "guest-jwt" } }, error: null });
  mocks.api.mockResolvedValue({ project: { id: "northstar-project" } });
});

afterEach(cleanup);

describe("public guest demo", () => {
  it("creates an anonymous session with the guest_demo CAPTCHA before bootstrapping", async () => {
    renderEntry(false);

    const verification = screen.getByRole("button", { name: "Complete guest verification" });
    expect(verification).toHaveAttribute("data-action", "guest_demo");
    expect(screen.getByRole("link", { name: /persistent team workspace/i })).toHaveAttribute("href", "/login?next=%2Fdemo");
    fireEvent.click(verification);
    fireEvent.click(screen.getByRole("button", { name: /Open guest workspace/i }));

    await waitFor(() => expect(mocks.signInAnonymously).toHaveBeenCalledWith({ options: { captchaToken: "guest-captcha" } }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/v1/workspaces/bootstrap", expect.objectContaining({ method: "POST" })));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/projects/northstar-project/overview"));
  });

  it("bootstraps an existing session immediately without anonymous sign-in", async () => {
    renderEntry(true);
    await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(1));
    expect(mocks.signInAnonymously).not.toHaveBeenCalled();
    expect(screen.queryByText("Complete guest verification")).not.toBeInTheDocument();
  });
});
