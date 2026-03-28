import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl } from "@/app/api/_utils/upstream";

export async function POST(req: NextRequest) {
  const json = (await req.json().catch(() => null)) as { token?: string; require_role?: "admin" | "team" } | null;
  const token = (json?.token || "").trim();
  const requireRole = json?.require_role;

  if (!token) {
    return NextResponse.json({ error: "Missing token" }, { status: 400 });
  }

  // Validate token/JWT against config_service before setting any session cookie.
  // This prevents "bad cookie" sessions and enables OIDC-first flows (paste OIDC JWT or admin token).
  let identity: any = null;
  try {
    const base = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/auth/me", base);
    const r = await fetch(upstreamUrl, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const text = await r.text();
    if (!r.ok) {
      return new NextResponse(text || JSON.stringify({ error: "Invalid token" }), {
        status: r.status,
        headers: { "content-type": r.headers.get("content-type") || "application/json" },
      });
    }
    identity = text ? JSON.parse(text) : null;
  } catch (e: any) {
    return NextResponse.json({ error: "Failed to validate token", details: e?.message || String(e) }, { status: 502 });
  }

  if (!identity || !identity.role) {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }
  if (requireRole && identity.role !== requireRole) {
    return NextResponse.json({ error: `Role ${requireRole} required`, role: identity.role }, { status: 403 });
  }

  // Cookie security:
  // - In prod we want secure cookies.
  // - In local dev (SSM tunnel, http://localhost) we often need secure=false.
  const secure = (process.env.WEB_UI_COOKIE_SECURE || "0").trim() === "1";

  const res = NextResponse.json({ ok: true, identity });
  res.cookies.set({
    name: "opensre_session_token",
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });
  return res;
}


