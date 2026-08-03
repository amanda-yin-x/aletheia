"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpenText,
  FileCheck2,
  Github,
  Play,
  Search,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";

const commands = [
  { label: "Why policy CI matters", detail: "See the failure scenario", href: "#why", icon: ShieldCheck },
  { label: "How Aletheia works", detail: "Follow the four-stage release path", href: "#workflow", icon: Workflow },
  { label: "What the build produces", detail: "Inspect the release evidence", href: "#evidence", icon: FileCheck2 },
  { label: "Open the Northstar demo", detail: "Run the source-linked refund workflow", href: "/demo", icon: Play },
  {
    label: "Read the production roadmap",
    detail: "Current state, correctness audit, and next steps",
    href: "https://github.com/amanda-yin-x/aletheia/blob/main/docs/current-state-and-production-roadmap.md",
    icon: BookOpenText,
    external: true,
  },
  {
    label: "View source on GitHub",
    detail: "amanda-yin-x/aletheia",
    href: "https://github.com/amanda-yin-x/aletheia",
    icon: Github,
    external: true,
  },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/") return <MarketingHeader />;
  return (
    <header className="site-header">
      <Link href="/" className="brand" aria-label="Aletheia home">
        <span className="brand-mark"><ShieldCheck size={18} strokeWidth={2.2} /></span>
        <span>Aletheia</span>
        <span className="brand-tag">Policy CI</span>
      </Link>
      <div className="header-note"><span className="status-dot" /> Deterministic demo</div>
    </header>
  );
}

function MarketingHeader() {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return commands;
    return commands.filter((command) => `${command.label} ${command.detail}`.toLocaleLowerCase().includes(needle));
  }, [query]);

  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery("");
    setSelected(0);
    if (!dialogRef.current?.open) dialogRef.current?.showModal();
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const closePalette = useCallback(() => {
    setOpen(false);
    if (dialogRef.current?.open) dialogRef.current.close();
  }, []);

  const visit = useCallback((command: (typeof commands)[number]) => {
    closePalette();
    if ("external" in command && command.external) {
      window.open(command.href, "_blank", "noopener,noreferrer");
      return;
    }
    if (command.href.startsWith("#")) {
      document.querySelector(command.href)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      window.history.replaceState(null, "", command.href);
      return;
    }
    router.push(command.href);
  }, [closePalette, router]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
        event.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openPalette]);

  return (
    <>
      <header className="marketing-header">
        <div className="marketing-header-inner">
          <Link href="/" className="marketing-brand" aria-label="Aletheia home">
            <span className="marketing-brand-mark"><ShieldCheck size={17} strokeWidth={2.2} /></span>
            <span className="marketing-wordmark">Aletheia</span>
            <span className="marketing-brand-product">Policy CI</span>
          </Link>
          <nav className="marketing-nav" aria-label="Marketing navigation">
            <a href="#why">Why it matters</a>
            <a href="#workflow">Workflow</a>
            <button className="command-trigger" type="button" onClick={openPalette} aria-haspopup="dialog" aria-expanded={open} aria-controls="jump-dialog" aria-label="Open jump menu">
              <Search size={15} aria-hidden="true" />
              <span aria-hidden="true">Jump to…</span>
              <kbd>⌘K</kbd>
            </button>
            <Link className="marketing-nav-cta" href="/demo">Open demo <ArrowRight size={15} aria-hidden="true" /></Link>
          </nav>
        </div>
      </header>

      <dialog
        ref={dialogRef}
        id="jump-dialog"
        className="command-dialog"
        aria-labelledby="jump-dialog-title"
        onCancel={(event) => { event.preventDefault(); closePalette(); }}
        onClose={() => setOpen(false)}
        onClick={(event) => { if (event.target === event.currentTarget) closePalette(); }}
      >
        <div className="command-dialog-head">
          <div><small>Quick navigation</small><strong id="jump-dialog-title">Jump to a page or section</strong></div>
          <button className="command-close" type="button" onClick={closePalette} aria-label="Close jump menu"><X size={18} aria-hidden="true" /></button>
        </div>
        <div className="command-field">
          <Search size={18} aria-hidden="true" />
          <div className="command-input-wrap">
            <label htmlFor="command-search">Search destinations</label>
            <input
              id="command-search"
              ref={inputRef}
              value={query}
              onChange={(event) => { setQuery(event.target.value); setSelected(0); }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setSelected((value) => filtered.length ? (value + 1) % filtered.length : 0);
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setSelected((value) => filtered.length ? (value - 1 + filtered.length) % filtered.length : 0);
                }
                if (event.key === "Enter" && filtered[selected]) {
                  event.preventDefault();
                  visit(filtered[selected]);
                }
              }}
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-controls="command-results"
              aria-activedescendant={filtered[selected] ? `command-${selected}` : undefined}
              placeholder="Try “demo” or “workflow”"
            />
          </div>
          <kbd>Esc</kbd>
        </div>
        <div id="command-results" className="command-results" role="listbox" aria-label="Destinations">
          {filtered.length ? filtered.map((command, index) => {
            const Icon = command.icon;
            return (
              <button
                id={`command-${index}`}
                key={command.label}
                className={index === selected ? "is-selected" : ""}
                type="button"
                role="option"
                aria-selected={index === selected}
                onMouseEnter={() => setSelected(index)}
                onClick={() => visit(command)}
              >
                <Icon size={17} aria-hidden="true" />
                <span><strong>{command.label}</strong><small>{command.detail}</small></span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            );
          }) : <p className="command-empty">No matching destination. Try “demo” or “workflow”.</p>}
        </div>
        <div className="command-hints" aria-hidden="true"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>
      </dialog>
    </>
  );
}
