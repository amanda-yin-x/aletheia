import { useEffect } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TurnstileWidget } from "@/components/turnstile-widget";

const mocks = vi.hoisted(() => ({
  options: null as Record<string, unknown> | null,
  ready: vi.fn((callback: () => void) => callback()),
  render: vi.fn((_element: HTMLElement, options: Record<string, unknown>) => {
    mocks.options = options;
    return "widget-1";
  }),
  reset: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("next/script", () => ({
  default: function MockScript({ onLoad, onReady }: { onLoad?: () => void; onReady?: () => void }) {
    useEffect(() => { onLoad?.(); onReady?.(); }, [onLoad, onReady]);
    return null;
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.options = null;
  window.turnstile = { ready: mocks.ready, render: mocks.render, reset: mocks.reset, remove: mocks.remove };
});

describe("Turnstile widget lifecycle", () => {
  it("uses explicit always-visible rendering and reports timeout failures", async () => {
    const onToken = vi.fn();
    const view = render(<TurnstileWidget siteKey="site-key" action="guest_demo" onToken={onToken} />);

    await waitFor(() => expect(mocks.render).toHaveBeenCalledTimes(1));
    expect(mocks.ready).toHaveBeenCalled();
    expect(mocks.options).toEqual(expect.objectContaining({ sitekey: "site-key", action: "guest_demo", appearance: "always" }));
    expect(screen.getByText("Complete the verification to continue.")).toBeInTheDocument();

    act(() => { (mocks.options?.["timeout-callback"] as () => void)(); });
    expect(screen.getByRole("alert")).toHaveTextContent("Verification timed out. Try again.");
    expect(onToken).toHaveBeenLastCalledWith(null);

    view.unmount();
    expect(mocks.reset).toHaveBeenCalledWith("widget-1");
    expect(mocks.remove).toHaveBeenCalledWith("widget-1");
  });
});
