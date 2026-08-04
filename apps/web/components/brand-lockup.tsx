import type { SVGProps } from "react";

type BrandLockupSize = "compact" | "standard" | "large";

interface BrandLockupProps {
  className?: string;
  size?: BrandLockupSize;
  showWordmark?: boolean;
}

export function AthenaMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 72 72"
      fill="none"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      <path
        className="aletheia-mark-navy"
        d="M34.4 3.5 4.8 61.4c10.7-.5 19.5-5.2 23.6-12.7 3.9-7.1.7-11.1 1.1-16.7.4-6 4.9-10.5 4.9-19.1V3.5Z"
      />
      <path
        className="aletheia-mark-gold"
        d="M37.1 3.5 67.2 61.4c-10.6-.4-19.6-4.9-24.8-11.6-4-5.2-5.5-9.1-3.1-12.2 1.2-1.5 3.5-2.1 3.4-3.6-.1-1.1-2.4-2.5-3.1-4.4-1-2.8-2.5-5.5-2.5-9.3V3.5Z"
      />
      <path className="aletheia-mark-gold" d="M31.5 31.7c2-2.7 5-3.8 8.5-2.7-3.2-.1-5.7 1-7.5 3.6l-1-.9Z" />
      <path className="aletheia-mark-gold" d="M32.9 34.2c2.2 1.6 4.7 1.8 7.1.5-1.5 2.4-5.2 2.5-7.1-.5Z" />
      <path className="aletheia-mark-navy" d="M31 49.7C27.4 58.8 19.5 65 7.8 68.2h16.1c5.4-4.5 8.2-10.7 8.9-18.5H31Z" />
      <path className="aletheia-mark-steel" d="M34.1 50.4c-.2 7.8-1.7 13.7-4.6 17.8h9.1c-.9-7.8-1.8-13.7-2.9-17.8h-1.6Z" />
      <path className="aletheia-mark-gold" d="M38.1 49.7c3.9 9.1 12.2 15.3 24.1 18.5H50.8c-7-4.3-11.5-10.5-14.4-18.5h1.7Z" />
    </svg>
  );
}

export function BrandLockup({ className = "", size = "standard", showWordmark = true }: BrandLockupProps) {
  const classes = ["aletheia-lockup", `aletheia-lockup-${size}`, className].filter(Boolean).join(" ");
  return (
    <span className={classes}>
      <AthenaMark className="aletheia-lockup-mark" />
      {showWordmark && <span className="aletheia-lockup-wordmark" aria-hidden="true">ALETHEIA</span>}
      <span className="sr-only">Aletheia</span>
    </span>
  );
}
