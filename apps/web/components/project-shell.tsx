"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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

function routeIsActive(pathname: string, hash: string, projectId: string, name: string, route: string) {
  const segment = route.split("#")[0];
  const destination = `/projects/${projectId}/${segment}`;
  const destinationIsActive = pathname === destination
    || pathname.startsWith(`${destination}/`)
    || (name === "Build" && pathname.startsWith(`/projects/${projectId}/builds/`));
  if (name === "Report") return destinationIsActive && hash === "#latest-report";
  if (name === "Overview" && hash === "#latest-report") return false;
  return destinationIsActive;
}

export function ProjectShell({ projectId, children }: { projectId: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const [hash, setHash] = useState("");
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api<Project>(`/api/v1/projects/${projectId}`),
  });
  useEffect(() => {
    const readHash = () => setHash(window.location.hash);
    readHash();
    window.addEventListener("hashchange", readHash);
    return () => window.removeEventListener("hashchange", readHash);
  }, [pathname]);
  const projectName = project.data?.name || "Policy project";
  const projectContext = project.data?.domain
    ? `${label(project.data.domain)} domain`
    : project.isError
      ? "Project context unavailable"
      : "Loading project context";
  const dataScope = project.data?.mode === "demo" ? "Evaluation records" : "Review source metadata";
  const errorMessage = project.error instanceof Error
    ? project.error.message
    : "Project details could not be loaded.";
  return <div className="workspace-layout">
    <aside className="project-rail" aria-label="Project navigation">
      <div className="rail-context">
        <span className="workspace-label">Policy workspace</span>
        <strong>{projectName}</strong>
        <small>{projectContext}</small>
      </div>
      <nav aria-label="Project sections">
        {items.map(([name, route, Icon]) => {
          const href = `/projects/${projectId}/${route}`;
          const active = routeIsActive(pathname, hash, projectId, name, route);
          return <Link
            key={name}
            href={href}
            className={active ? "active" : undefined}
            aria-label={name}
            aria-current={active ? (name === "Report" ? "location" : "page") : undefined}
          >
            <Icon size={17} aria-hidden="true" />
            <span>{name}</span>
          </Link>;
        })}
      </nav>
      <div className="rail-note"><span className="status-dot" /> Project data scope<br /><small>{dataScope}</small></div>
    </aside>
    <main className="workspace-main">
      {project.isError && <section className="project-shell-error" role="alert" aria-label="Project details error">
        <div>
          <strong>Project details are unavailable.</strong>
          <p>{errorMessage}</p>
        </div>
        <button
          className="button button-secondary button-small"
          type="button"
          onClick={() => void project.refetch()}
          disabled={project.isFetching}
        >
          {project.isFetching ? "Retrying…" : "Retry project details"}
        </button>
      </section>}
      {children}
    </main>
  </div>;
}
