"use client";

import { useParams } from "next/navigation";
import { PlacementWorkbench } from "@/features/placement-workbench";

export default function RoutingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  return <PlacementWorkbench projectId={projectId} />;
}
