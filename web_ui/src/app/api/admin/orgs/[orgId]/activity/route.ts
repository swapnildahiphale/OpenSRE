import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

// GET /api/admin/orgs/:orgId/activity - Get recent activity feed
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ orgId: string }> },
) {
  try {
    const { orgId } = await ctx.params;
    const baseUrl = getConfigServiceBaseUrl();

    // Get query parameters for pagination/filtering (e.g., limit, offset, type)
    const { searchParams } = new URL(req.url);
    const queryString = searchParams.toString();
    const upstreamUrl = new URL(
      `/api/v1/admin/orgs/${orgId}/activity${queryString ? `?${queryString}` : ''}`,
      baseUrl
    );

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
      { error: "Failed to get activity feed", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}
