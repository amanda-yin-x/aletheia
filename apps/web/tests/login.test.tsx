import { useEffect } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/app/login/login-form";

const mocks = vi.hoisted(() => ({
  send: vi.fn(async () => ({ error: null })),
  updateUser: vi.fn(async () => ({ error: null })),
  verifyOtp: vi.fn(async () => ({ error: null })),
  signInWithOAuth: vi.fn(async () => ({ error: null })),
  linkIdentity: vi.fn(async () => ({ error: null })),
  widgetMounted: vi.fn(),
}));

vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({
    auth: {
      signInWithOtp: mocks.send,
      updateUser: mocks.updateUser,
      verifyOtp: mocks.verifyOtp,
      signInWithOAuth: mocks.signInWithOAuth,
      linkIdentity: mocks.linkIdentity,
    },
  }),
}));

vi.mock("@/components/turnstile-widget", () => ({
  TurnstileWidget: ({ action, onToken }: { action: string; onToken: (token: string) => void }) => {
    useEffect(() => { mocks.widgetMounted(); }, []);
    return <button type="button" data-action={action} onClick={() => onToken("captcha-once")}>Complete verification</button>;
  },
}));

afterEach(cleanup);

describe("email sign in", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("discards and remounts Turnstile after each attempted request", async () => {
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "site-key", siteUrl: "https://aletheia.example", githubAuthEnabled: false, emailOtpEnabled: false }} nextPath="/demo" hasAnonymousSession={false} />);
    expect(screen.getByRole("link", { name: /Open the no-account demo/i })).toHaveAttribute("href", "/demo");
    expect(screen.getByRole("heading", { name: "Keep a workspace across visits." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete verification" })).toHaveAttribute("data-action", "login");
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Complete verification" }));
    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));

    await waitFor(() => expect(mocks.send).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.widgetMounted).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Check your email for a secure, single-use sign-in link.")).toBeInTheDocument();
    expect(screen.queryByLabelText("One-time code")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));
    expect(await screen.findByText("Complete the verification before requesting a sign-in link.")).toBeInTheDocument();
    expect(mocks.send).toHaveBeenCalledTimes(1);
  });

  it("links email to the anonymous user in place so its subject-backed workspace survives", async () => {
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "site-key", siteUrl: "https://aletheia.example", githubAuthEnabled: false, emailOtpEnabled: false }} nextPath="/projects/northstar" hasAnonymousSession />);

    expect(screen.queryByRole("button", { name: "Complete verification" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "  guest@example.com  " } });
    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));

    await waitFor(() => expect(mocks.updateUser).toHaveBeenCalledWith(
      { email: "guest@example.com" },
      { emailRedirectTo: "https://aletheia.example/auth/callback?next=%2Fprojects%2Fnorthstar" },
    ));
    expect(mocks.send).not.toHaveBeenCalled();
  });
});

describe("GitHub sign in", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("links GitHub to the anonymous user instead of replacing its subject", async () => {
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "", siteUrl: "https://aletheia.example", githubAuthEnabled: true, emailOtpEnabled: false }} nextPath="/demo" hasAnonymousSession />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with GitHub" }));

    await waitFor(() => expect(mocks.linkIdentity).toHaveBeenCalledWith({
      provider: "github",
      options: { redirectTo: "https://aletheia.example/auth/callback?next=%2Fdemo" },
    }));
    expect(mocks.signInWithOAuth).not.toHaveBeenCalled();
  });

  it("uses ordinary OAuth when there is no anonymous identity to preserve", async () => {
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "", siteUrl: "https://aletheia.example", githubAuthEnabled: true, emailOtpEnabled: false }} nextPath="/demo" hasAnonymousSession={false} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with GitHub" }));

    await waitFor(() => expect(mocks.signInWithOAuth).toHaveBeenCalledWith({
      provider: "github",
      options: { redirectTo: "https://aletheia.example/auth/callback?next=%2Fdemo" },
    }));
    expect(mocks.linkIdentity).not.toHaveBeenCalled();
  });
});
