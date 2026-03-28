import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

// GET /api/admin/orgs/:orgId/tokens/:tokenId - Get token details
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ orgId: string; tokenId: string }> },
) {
  try {
    const { orgId, tokenId } = await ctx.params;
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL(`/api/v1/admin/orgs/${orgId}/tokens/${tokenId}`, baseUrl);

    const authHeaders = getUpstreamAuthHeaders(req);
    const actor = req.headers.get("x-admin-actor");
    const headers: Record<string, string> = { ...authHeaders };
    if (actor) headers["X-Admin-Actor"] = actor;

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: Object.keys(headers).length ? headers : undefined,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();
    return new NextResponse(body, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to get token details", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}
