import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { CSRF_COOKIE_NAME } from "@/lib/security";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(CSRF_COOKIE_NAME)?.value || crypto.randomUUID();
  const response = NextResponse.json({ token });
  response.cookies.set(CSRF_COOKIE_NAME, token, {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
