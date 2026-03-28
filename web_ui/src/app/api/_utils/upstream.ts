import { NextRequest } from "next/server";

export const runtime = "nodejs";

export function getConfigServiceBaseUrl() {
  const baseUrl = process.env.CONFIG_SERVICE_URL;
  if (!baseUrl) throw new Error("CONFIG_SERVICE_URL is not set");
  return baseUrl;
}

export function getOrchestratorBaseUrl() {
  const baseUrl = process.env.ORCHESTRATOR_URL;
  if (!baseUrl) throw new Error("ORCHESTRATOR_URL is not set");
  return baseUrl;
}

export function getUpstreamAuthHeaders(req: NextRequest): Record<string, string> {
  // Support both:
  // - Authorization: Bearer <token>
  // - X-Admin-Token: <token>
  const headers: Record<string, string> = {};

  const auth = req.headers.get("authorization");
  if (auth && auth.toLowerCase().startsWith("bearer ")) {
    headers.Authorization = auth;
  }

  const xAdminToken = req.headers.get("x-admin-token");
  if (xAdminToken) {
    headers["X-Admin-Token"] = xAdminToken;
  }

  // Enterprise default: token stored in httpOnly cookie set by /api/session/login.
  // If the client doesn't provide Authorization, fall back to cookie.
  if (!headers.Authorization) {
    const cookieToken = req.cookies.get("opensre_session_token")?.value;
    if (cookieToken) {
      headers.Authorization = `Bearer ${cookieToken}`;
    }
  }

  return headers;
}

export async function requireAdminSession(req: NextRequest): Promise<any> {
  const baseUrl = getConfigServiceBaseUrl();
  const upstreamUrl = new URL("/api/v1/auth/me", baseUrl);
  const authHeaders = getUpstreamAuthHeaders(req);
  if (!Object.keys(authHeaders).length) {
    throw new Error("missing_auth");
  }
  const res = await fetch(upstreamUrl, {
    method: "GET",
    headers: authHeaders,
    cache: "no-store",
  });
  const text = await res.text();
  if (!res.ok) {
    const err = new Error(`auth_failed:${res.status}`);
    // @ts-ignore
    err.status = res.status;
    // @ts-ignore
    err.body = text;
    throw err;
  }
  const identity = text ? JSON.parse(text) : null;
  if (!identity || identity.role !== "admin") {
    const err = new Error("admin_required");
    // @ts-ignore
    err.status = 403;
    throw err;
  }
  return identity;
}


