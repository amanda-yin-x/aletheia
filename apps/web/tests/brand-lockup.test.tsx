import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AthenaMark, BrandLockup } from "@/components/brand-lockup";

afterEach(cleanup);

describe("Aletheia brand lockup", () => {
  it("pairs a decorative navy-and-gold Athena mark with an accessible classical wordmark", () => {
    const { container } = render(<BrandLockup size="large" />);

    expect(screen.getByText("ALETHEIA")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Aletheia")).toHaveClass("sr-only");
    expect(container.firstElementChild).toHaveClass("aletheia-lockup-large");
    expect(container.querySelector("svg")).toHaveAttribute("viewBox", "0 0 72 72");
    expect(container.querySelector(".aletheia-mark-navy")).toBeInTheDocument();
    expect(container.querySelector(".aletheia-mark-gold")).toBeInTheDocument();
  });

  it("keeps the standalone mark decorative and removes the visible wordmark when requested", () => {
    const { container } = render(<><AthenaMark /><BrandLockup showWordmark={false} /></>);

    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByText("ALETHEIA")).not.toBeInTheDocument();
    expect(screen.getByText("Aletheia")).toBeInTheDocument();
  });
});
