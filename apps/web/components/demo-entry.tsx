"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { API_IS_CONFIGURED, api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { EmptyState, ErrorState, PageLoading } from "@/components/ui";

export function DemoEntry() {
  if (!API_IS_CONFIGURED) {
    return (
      <main className="landing">
        <EmptyState
          title="The hosted workspace needs its API connection."
          detail="The website is live on Cloudflare. The interactive Northstar workflow still runs from the checked-in FastAPI service and database; it has not been exposed as a shared anonymous service."
          action={<div className="page-actions"><a className="button button-primary" href="https://github.com/amanda-yin-x/aletheia#quick-start">Run it locally</a><a className="button button-secondary" href="https://github.com/amanda-yin-x/aletheia/blob/main/docs/deployment.md">Read deployment notes</a></div>}
        />
      </main>
    );
  }
  return <ConnectedDemo />;
}

function ConnectedDemo() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/v1/projects") });
  useEffect(() => { if (query.data?.[0]) router.replace(`/projects/${query.data[0].id}/overview`); }, [query.data, router]);
  if (query.error) return <main className="landing"><ErrorState error={query.error} onRetry={() => query.refetch()} /></main>;
  return <main className="landing"><PageLoading label="Opening the Northstar policy workspace" /></main>;
}
