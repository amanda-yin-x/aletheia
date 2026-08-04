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
    expect(screen.getByRole("heading", { name: "Keep a personal Northstar workspace across visits." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete verification" })).toHaveAttribute("data-action", "login");
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Complete verification" }));
    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));

    await waitFor(() => expect(mocks.send).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.widgetMounted).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("status")).toHaveTextContent("Check your email for a secure, single-use sign-in link.");
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

  it("recovers the GitHub control and announces a rejected network request", async () => {
    mocks.signInWithOAuth.mockRejectedValueOnce(new Error("offline"));
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "", siteUrl: "https://aletheia.example", githubAuthEnabled: true, emailOtpEnabled: false }} nextPath="/demo" hasAnonymousSession={false} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with GitHub" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("GitHub sign-in could not start");
    expect(screen.getByRole("button", { name: "Continue with GitHub" })).toBeEnabled();
  });
});

describe("one-time code verification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("recovers the OTP control and announces a rejected network request", async () => {
    mocks.verifyOtp.mockRejectedValueOnce(new Error("offline"));
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "", siteUrl: "https://aletheia.example", githubAuthEnabled: false, emailOtpEnabled: true }} nextPath="/demo" hasAnonymousSession={false} />);

    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));
    const otp = await screen.findByLabelText("One-time code");
    fireEvent.change(otp, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The one-time code could not be verified");
    expect(screen.getByRole("button", { name: "Verify code" })).toBeEnabled();
  });
});
