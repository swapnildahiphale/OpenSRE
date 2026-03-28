import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

export async function GET(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: Object.keys(authHeaders).length ? authHeaders : undefined,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();
    const data = JSON.parse(body);

    // v2 API returns {effective_config: {...}, ...}, extract the config
    const config = data.effective_config || data;

    return new NextResponse(JSON.stringify(config), { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to fetch effective config", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}


