import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

/**
 * GET /api/config/me
 *
 * Get the effective configuration for the current team.
 */
export async function GET(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: authHeaders,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to get team config", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}

/**
 * PATCH /api/config/me
 *
 * Patch (deep merge) the team configuration.
 */
export async function PATCH(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const body = await req.json();

    // v2 API expects {config: ...} format
    const payload = {
      config: body,
    };

    const res = await fetch(upstreamUrl, {
      method: "PATCH",
      headers: {
        ...authHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to update team config", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}

/**
 * PUT /api/config/me (legacy - same as PATCH)
 */
export async function PUT(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const body = await req.text();
    const bodyJson = JSON.parse(body);

    // v2 API expects {config: ...} format
    const payload = {
      config: bodyJson,
    };

    const res = await fetch(upstreamUrl, {
      method: "PATCH",
      headers: {
        ...authHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to update team config", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}


