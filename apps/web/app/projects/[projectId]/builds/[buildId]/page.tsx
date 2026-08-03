"use client";

import { useParams } from "next/navigation";
import { BuildWorkbench } from "@/features/build-workbench";

export default function BuiltPage() {
  const { projectId, buildId } = useParams<{ projectId: string; buildId: string }>();
  return <BuildWorkbench projectId={projectId} requestedBuildId={buildId} />;
}

