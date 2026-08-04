import { NextResponse } from "next/server";
import { getAuthIdentity } from "@/lib/supabase/auth";

export async function GET() {
  const identity = await getAuthIdentity();
  const response = identity
    ? NextResponse.json({ user: identity })
    : NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Vary", "Cookie");
  return response;
}
