import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ orgId: string; teamNodeId: string; tokenId: string }> },
) {
  try {
    const { orgId, teamNodeId, tokenId } = await ctx.params;
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL(
      `/api/v1/admin/orgs/${orgId}/teams/${teamNodeId}/tokens/${tokenId}/revoke`,
      baseUrl,
    );

    const authHeaders = getUpstreamAuthHeaders(req);
    const actor = req.headers.get("x-admin-actor");
    const headers: Record<string, string> = { ...authHeaders };
    if (actor) headers["X-Admin-Actor"] = actor;

    const res = await fetch(upstreamUrl, {
      method: "POST",
      headers: Object.keys(headers).length ? headers : undefined,
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();
    return new NextResponse(body, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to revoke token", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}


