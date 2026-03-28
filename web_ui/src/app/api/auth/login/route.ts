import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export const runtime = "nodejs";

function base64url(buf: Buffer) {
  return buf
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function getOidcEnv() {
  const enabled = (process.env.WEB_UI_OIDC_ENABLED || "0").trim() === "1";
  const authorizationEndpoint = (process.env.WEB_UI_OIDC_AUTHORIZATION_ENDPOINT || "").trim();
  const clientId = (process.env.WEB_UI_OIDC_CLIENT_ID || "").trim();
  const scope = (process.env.WEB_UI_OIDC_SCOPES || "openid email profile groups").trim();
  const publicBaseUrl = (process.env.WEB_UI_PUBLIC_BASE_URL || "").trim();
  return { enabled, authorizationEndpoint, clientId, scope, publicBaseUrl };
}

function getRedirectUri(req: NextRequest) {
  const env = getOidcEnv();
  const origin =
    env.publicBaseUrl ||
    `${req.headers.get("x-forwarded-proto") || req.nextUrl.protocol.replace(":", "")}://${req.headers.get("x-forwarded-host") || req.headers.get("host")}`;
  return `${origin}/api/auth/callback`;
}

export async function GET(req: NextRequest) {
  const env = getOidcEnv();
  if (!env.enabled) {
    return NextResponse.json({ error: "OIDC is not enabled" }, { status: 404 });
  }
  if (!env.authorizationEndpoint || !env.clientId) {
    return NextResponse.json({ error: "OIDC is not configured" }, { status: 500 });
  }

  const secure = (process.env.WEB_UI_COOKIE_SECURE || "0").trim() === "1";
  const state = base64url(crypto.randomBytes(32));
  const verifier = base64url(crypto.randomBytes(32));
  const challenge = base64url(crypto.createHash("sha256").update(verifier).digest());

  const requireRole = (req.nextUrl.searchParams.get("require_role") || "").trim();

  const redirectUri = getRedirectUri(req);
  const u = new URL(env.authorizationEndpoint);
  u.searchParams.set("response_type", "code");
  u.searchParams.set("client_id", env.clientId);
  u.searchParams.set("redirect_uri", redirectUri);
  u.searchParams.set("scope", env.scope);
  u.searchParams.set("state", state);
  u.searchParams.set("code_challenge", challenge);
  u.searchParams.set("code_challenge_method", "S256");

  const res = NextResponse.redirect(u.toString(), 302);
  // Short-lived temporary cookies for callback validation.
  res.cookies.set({
    name: "ifx_oidc_state",
    value: state,
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/api/auth/callback",
    maxAge: 60 * 10,
  });
  res.cookies.set({
    name: "ifx_oidc_verifier",
    value: verifier,
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/api/auth/callback",
    maxAge: 60 * 10,
  });
  if (requireRole) {
    res.cookies.set({
      name: "ifx_oidc_require_role",
      value: requireRole,
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/api/auth/callback",
      maxAge: 60 * 10,
    });
  }
  return res;
}


