"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { api, RequestError } from "@/lib/api";
import type { BootstrapResult, Project } from "@/lib/types";
import { ErrorState, PageLoading } from "@/components/ui";

type BootstrapCompatibility = BootstrapResult | Project | { project?: Project; project_id?: string };

function projectIdFromBootstrap(value: BootstrapCompatibility): string | null {
  if ("project" in value && value.project?.id) return value.project.id;
  if ("project_id" in value && value.project_id) return value.project_id;
  if ("slug" in value && value.id) return value.id;
  return null;
}

export function DemoEntry() {
  const router = useRouter();
  const started = useRef(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [waking, setWaking] = useState(false);
  const bootstrap = useMutation({
    mutationFn: async () => {
      const value = await api<BootstrapCompatibility>("/api/v1/workspaces/bootstrap", {
        method: "POST",
        body: JSON.stringify({ name: "My workspace" }),
        retryMutation: true,
        coldStartRetries: 20,
        coldStartTimeoutMs: 85_000,
        onRetry: () => setWaking(true),
        idempotencyKey: idempotencyKey.current,
      });
      const projectId = projectIdFromBootstrap(value);
      if (!projectId) throw new Error("The workspace opened without a project identifier.");
      return projectId;
    },
    onMutate: () => setWaking(false),
    onSuccess: (projectId) => router.replace(`/projects/${projectId}/overview`),
    onError: (error) => {
      if (error instanceof RequestError && error.status === 401) router.replace("/login?next=%2Fdemo");
    },
  });

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    bootstrap.mutate();
  }, [bootstrap]);

  if (bootstrap.error) {
    return <main className="landing"><ErrorState error={bootstrap.error} onRetry={() => { setWaking(false); idempotencyKey.current = crypto.randomUUID(); bootstrap.reset(); bootstrap.mutate(); }} /></main>;
  }
  return <main className="landing"><PageLoading label={waking ? "Waking your workspace…" : "Preparing your Northstar policy workspace"} /></main>;
}
