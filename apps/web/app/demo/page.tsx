"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ErrorState, PageLoading } from "@/components/ui";

export default function DemoPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/api/v1/projects") });
  useEffect(() => { if (query.data?.[0]) router.replace(`/projects/${query.data[0].id}/overview`); }, [query.data, router]);
  if (query.error) return <main className="landing"><ErrorState error={query.error} onRetry={() => query.refetch()} /></main>;
  return <main className="landing"><PageLoading label="Opening the Northstar refund demo" /></main>;
}

