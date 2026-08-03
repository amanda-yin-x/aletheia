"use client";

import { useParams } from "next/navigation";
import { BuildWorkbench } from "@/features/build-workbench";

export default function BuildPage() {
  const { projectId } = useParams<{ projectId: string }>();
  return <BuildWorkbench projectId={projectId} />;
}

