"use client";

import { AlertCircle, ArrowRight, CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { RequestError } from "@/lib/api";

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "blue" | "teal" | "amber" | "red" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Button({ children, variant = "primary", className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}

export function LinkButton({ children, href, variant = "primary" }: { children: React.ReactNode; href: string; variant?: "primary" | "secondary" }) {
  return <Link className={`button button-${variant}`} href={href}>{children}</Link>;
}

export function PageLoading({ label = "Loading workspace", detail = "Reading persisted release artifacts…" }: { label?: string; detail?: string }) {
  return <div className="state-panel" role="status"><LoaderCircle className="spin" size={22} /><strong>{label}</strong><span>{detail}</span></div>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const request = error instanceof RequestError ? error : null;
  const message = request?.message || (error instanceof Error ? error.message : "This view could not be loaded.");
  return <div className="state-panel state-error" role="alert"><AlertCircle size={24} /><strong>{message}</strong><span>Request ID: <code>{request?.payload.request_id || "not available"}</code></span>{onRetry && <Button variant="secondary" onClick={onRetry}><RefreshCw size={15} /> Retry</Button>}</div>;
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: React.ReactNode }) {
  return <div className="state-panel"><CheckCircle2 size={24} /><strong>{title}</strong><span>{detail}</span>{action}</div>;
}

export function PageTitle({ eyebrow, title, detail, actions }: { eyebrow?: string; title: string; detail: string; actions?: React.ReactNode }) {
  return <div className="page-title"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1><p>{detail}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>;
}

export function StatCard({ label, value, note, tone }: { label: string; value: React.ReactNode; note: string; tone?: string }) {
  return <div className={`stat-card ${tone ? `stat-${tone}` : ""}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>;
}

export function ArrowLabel({ children }: { children: React.ReactNode }) { return <span className="arrow-label">{children}<ArrowRight size={14} /></span>; }
