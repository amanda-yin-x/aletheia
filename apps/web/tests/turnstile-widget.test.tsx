import { useEffect } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TurnstileWidget } from "@/components/turnstile-widget";

const mocks = vi.hoisted(() => ({
  options: null as Record<string, unknown> | null,
  ready: vi.fn((callback: () => void) => callback()),
  render: vi.fn((_element: HTMLElement, options: Record<string, unknown>) => {
    mocks.options = options;
    return `widget-${mocks.render.mock.calls.length}`;
  }),
  reset: vi.fn(),
  remove: vi.fn(),
  scripts: [] as Array<{ src: string; onLoad?: () => void; onReady?: () => void; onError?: () => void }>,
}));

vi.mock("next/script", () => ({
  default: function MockScript({ src, onLoad, onReady, onError }: { src: string; onLoad?: () => void; onReady?: () => void; onError?: () => void }) {
    useEffect(() => { mocks.scripts.push({ src, onLoad, onReady, onError }); }, [src, onLoad, onReady, onError]);
    return null;
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.options = null;
  mocks.scripts.length = 0;
  window.turnstile = { ready: mocks.ready, render: mocks.render, reset: mocks.reset, remove: mocks.remove };
});

afterEach(cleanup);

describe("Turnstile widget lifecycle", () => {
  it("removes and re-renders a timed-out widget when the visitor retries", async () => {
    const onToken = vi.fn();
    const view = render(<TurnstileWidget siteKey="site-key" action="guest_demo" onToken={onToken} />);

    await waitFor(() => expect(mocks.render).toHaveBeenCalledTimes(1));
    expect(mocks.ready).toHaveBeenCalled();
    expect(mocks.options).toEqual(expect.objectContaining({ sitekey: "site-key", action: "guest_demo", appearance: "always" }));
    expect(screen.getByText("Complete the verification to continue.")).toBeInTheDocument();

    act(() => { (mocks.options?.["timeout-callback"] as () => void)(); });
    expect(screen.getByRole("alert")).toHaveTextContent("Verification timed out. Try again.");
    expect(onToken).toHaveBeenLastCalledWith(null);
    fireEvent.click(screen.getByRole("button", { name: "Retry verification" }));

    await waitFor(() => expect(mocks.render).toHaveBeenCalledTimes(2));
    expect(mocks.reset).toHaveBeenCalledWith("widget-1");
    expect(mocks.remove).toHaveBeenCalledWith("widget-1");
    expect(screen.getByText("Complete the verification to continue.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry verification" })).not.toBeInTheDocument();

    view.unmount();
    expect(mocks.reset).toHaveBeenCalledWith("widget-2");
    expect(mocks.remove).toHaveBeenCalledWith("widget-2");
  });

  it("remounts a failed script with a deterministic retry URL before rendering", async () => {
    const onToken = vi.fn();
    window.turnstile = undefined;
    render(<TurnstileWidget siteKey="site-key" action="login" onToken={onToken} />);

    await waitFor(() => expect(mocks.scripts).toHaveLength(1));
    act(() => { mocks.scripts[0].onError?.(); });
    expect(screen.getByRole("alert")).toHaveTextContent("Verification could not load.");

    fireEvent.click(screen.getByRole("button", { name: "Retry verification" }));
    await waitFor(() => expect(mocks.scripts.some((script) => script.src.endsWith("&retry=1"))).toBe(true));
    expect([...new Set(mocks.scripts.map((script) => script.src))]).toEqual([
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&retry=1",
    ]);

    window.turnstile = { ready: mocks.ready, render: mocks.render, reset: mocks.reset, remove: mocks.remove };
    act(() => { mocks.scripts.findLast((script) => script.src.endsWith("&retry=1"))?.onLoad?.(); });
    await waitFor(() => expect(mocks.render).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Complete the verification to continue.")).toBeInTheDocument();
  });
});
