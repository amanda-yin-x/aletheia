import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WaitlistForm } from "@/components/waitlist-form";

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  signInAnonymously: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(),
  api: mocks.api,
}));
vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({ auth: { signInAnonymously: mocks.signInAnonymously, signOut: mocks.signOut } }),
}));
vi.mock("@/components/turnstile-widget", () => ({
  TurnstileWidget: ({ action, onToken }: { action: string; onToken: (token: string) => void }) => (
    <button type="button" data-action={action} onClick={() => onToken("waitlist-captcha")}>Complete waitlist verification</button>
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

beforeEach(() => {
  vi.clearAllMocks();
  mocks.signInAnonymously.mockResolvedValue({ data: { session: { access_token: "guest-jwt" } }, error: null });
  mocks.signOut.mockResolvedValue({ error: null });
  mocks.api.mockResolvedValue({ joined: true });
});

afterEach(cleanup);

describe("landing waitlist", () => {
  it("creates a verified anonymous session before a visitor submits", async () => {
    render(<WaitlistForm config={config} initialHasSession={false} />);
    expect(screen.getByRole("heading", { name: "Keep a personal Northstar workspace." })).toBeInTheDocument();
    expect(screen.getByText("Personal workspace across visits")).toBeInTheDocument();
    expect(screen.queryByText(/team projects/i)).not.toBeInTheDocument();
    const verification = screen.getByRole("button", { name: "Complete waitlist verification" });
    expect(verification).toHaveAttribute("data-action", "waitlist");
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "owner@example.com" } });
    fireEvent.click(verification);
    fireEvent.click(screen.getByRole("button", { name: /Request preview access/i }));

    await waitFor(() => expect(mocks.signInAnonymously).toHaveBeenCalledWith({ options: { captchaToken: "waitlist-captcha" } }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/api/v1/waitlist", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ email: "owner@example.com" }),
    })));
    expect(await screen.findByText("Request saved. No email has been sent.")).toBeInTheDocument();
  });

  it("posts directly when a session already exists", async () => {
    render(<WaitlistForm config={config} initialHasSession />);
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "member@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Request preview access/i }));

    await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(1));
    expect(mocks.signInAnonymously).not.toHaveBeenCalled();
    expect(screen.queryByText("Complete waitlist verification")).not.toBeInTheDocument();
  });

  it("clears an expired guest session and restores verification", async () => {
    const { RequestError } = await import("@/lib/api");
    mocks.api.mockRejectedValueOnce(new RequestError({
      code: "guest_session_expired",
      message: "This guest demo has expired.",
      details: {},
      request_id: "request-1",
    }, 401));
    render(<WaitlistForm config={config} initialHasSession />);
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "member@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Request preview access/i }));

    expect(await screen.findByText(/guest session ended/i)).toBeInTheDocument();
    expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(screen.getByRole("button", { name: "Complete waitlist verification" })).toBeInTheDocument();
  });
});
