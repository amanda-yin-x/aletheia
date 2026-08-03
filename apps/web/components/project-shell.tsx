"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, FlaskConical, Gauge, Hammer, ScrollText, ShieldCheck } from "lucide-react";

const items = [
  ["Overview", "overview", Gauge],
  ["Sources", "sources", FileText],
  ["Rules", "rules", ShieldCheck],
  ["Build", "build", Hammer],
  ["Tests", "tests", FlaskConical],
  ["Report", "overview#latest-report", ScrollText],
] as const;

export function ProjectShell({ projectId, children }: { projectId: string; children: React.ReactNode }) {
  const pathname = usePathname();
  return <div className="workspace-layout">
    <aside className="project-rail" aria-label="Project navigation">
      <div className="rail-context">
        <span className="demo-label">Demo project</span>
        <strong>Northstar Retail</strong>
        <small>Refund agent</small>
      </div>
      <nav>
        {items.map(([name, route, Icon]) => {
          const href = `/projects/${projectId}/${route}`;
          const segment = route.split("#")[0];
          const active = pathname.includes(`/${segment}`) || (name === "Build" && pathname.includes("/builds/"));
          return <Link key={name} href={href} className={active ? "active" : ""}><Icon size={17} /><span>{name}</span></Link>;
        })}
      </nav>
      <div className="rail-note"><span className="status-dot" /> Synthetic data<br /><small>No customer records</small></div>
    </aside>
    <main className="workspace-main">{children}</main>
  </div>;
}

