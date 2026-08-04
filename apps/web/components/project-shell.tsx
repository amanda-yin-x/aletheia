"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, FlaskConical, Gauge, Hammer, ScrollText, ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, label } from "@/lib/api";
import type { Project } from "@/lib/types";

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
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api<Project>(`/api/v1/projects/${projectId}`),
  });
  const projectName = project.data?.name || "Policy project";
  const projectContext = project.data?.domain ? `${label(project.data.domain)} domain` : "Loading project context";
  const dataScope = project.data?.mode === "demo" ? "Evaluation records" : "Review source metadata";
  return <div className="workspace-layout">
    <aside className="project-rail" aria-label="Project navigation">
      <div className="rail-context">
        <span className="workspace-label">Policy workspace</span>
        <strong>{projectName}</strong>
        <small>{projectContext}</small>
      </div>
      <nav>
        {items.map(([name, route, Icon]) => {
          const href = `/projects/${projectId}/${route}`;
          const segment = route.split("#")[0];
          const active = pathname.includes(`/${segment}`) || (name === "Build" && pathname.includes("/builds/"));
          return <Link key={name} href={href} className={active ? "active" : ""}><Icon size={17} /><span>{name}</span></Link>;
        })}
      </nav>
      <div className="rail-note"><span className="status-dot" /> Project data scope<br /><small>{dataScope}</small></div>
    </aside>
    <main className="workspace-main">{children}</main>
  </div>;
}
