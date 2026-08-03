import type { Metadata } from "next";
import { Geist, Geist_Mono, Newsreader } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const displayFont = Newsreader({ subsets: ["latin"], weight: "variable", style: "normal", axes: ["opsz"], variable: "--font-newsreader", display: "swap" });
const bodyFont = Geist({ subsets: ["latin"], weight: "variable", variable: "--font-geist-sans", display: "swap" });
const monoFont = Geist_Mono({ subsets: ["latin"], weight: "variable", variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Aletheia — Policy CI for AI agents",
  description: "Find policy conflicts, compile reviewed tool guards, and test agent releases before consequential actions execute.",
  metadataBase: new URL("https://github.com/amanda-yin-x/aletheia"),
  openGraph: {
    title: "Aletheia — The release gate before an agent acts",
    description: "Source-linked policy review, deterministic tool guards, and repeatable release evidence.",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Aletheia — Policy CI for AI agents",
    description: "Review policy drift before an agent turns it into a side effect.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable}`}>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <Providers>
          <SiteHeader />
          <div id="main-content" tabIndex={-1}>{children}</div>
        </Providers>
      </body>
    </html>
  );
}
