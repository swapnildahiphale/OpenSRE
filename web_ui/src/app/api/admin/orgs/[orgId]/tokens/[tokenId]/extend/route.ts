import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

// POST /api/admin/orgs/:orgId/tokens/:tokenId/extend - Extend token expiration
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ orgId: string; tokenId: string }> },
) {
  try {
    const { orgId, tokenId } = await ctx.params;
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL(`/api/v1/admin/orgs/${orgId}/tokens/${tokenId}/extend`, baseUrl);

    const authHeaders = getUpstreamAuthHeaders(req);
    const actor = req.headers.get("x-admin-actor");
    const headers: Record<string, string> = {
      ...authHeaders,
      "Content-Type": "application/json",
    };
    if (actor) headers["X-Admin-Actor"] = actor;

    // Forward the request body (e.g., { "days": 90 })
    const body = await req.text();

    const res = await fetch(upstreamUrl, {
      method: "POST",
      headers: Object.keys(headers).length ? headers : undefined,
      body: body || undefined,
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const responseBody = await res.text();
    return new NextResponse(responseBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to extend token expiration", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}
