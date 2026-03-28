import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

// GET /api/admin/orgs/:orgId/health - Get system health status (services + integrations)
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ orgId: string }> },
) {
  try {
    const { orgId } = await ctx.params;
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL(`/api/v1/admin/orgs/${orgId}/health`, baseUrl);

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
      { error: "Failed to get system health", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}
