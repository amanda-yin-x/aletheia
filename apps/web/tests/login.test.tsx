import { useEffect } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/app/login/login-form";

const mocks = vi.hoisted(() => ({
  send: vi.fn(async () => ({ error: null })),
  widgetMounted: vi.fn(),
}));

vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({
    auth: {
      signInWithOtp: mocks.send,
      verifyOtp: vi.fn(),
      signInWithOAuth: vi.fn(),
    },
  }),
}));

vi.mock("@/components/turnstile-widget", () => ({
  TurnstileWidget: ({ onToken }: { onToken: (token: string) => void }) => {
    useEffect(() => { mocks.widgetMounted(); }, []);
    return <button type="button" onClick={() => onToken("captcha-once")}>Complete verification</button>;
  },
}));

describe("email sign in", () => {
  it("discards and remounts Turnstile after each attempted request", async () => {
    render(<LoginForm config={{ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "site-key", siteUrl: "https://aletheia.example" }} nextPath="/demo" />);
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Complete verification" }));
    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));

    await waitFor(() => expect(mocks.send).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.widgetMounted).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /Email me a sign-in link/i }));
    expect(await screen.findByText("Complete the verification before requesting a sign-in link.")).toBeInTheDocument();
    expect(mocks.send).toHaveBeenCalledTimes(1);
  });
});
