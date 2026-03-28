import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

export async function GET(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me/effective-trees", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: Object.keys(authHeaders).length ? authHeaders : undefined,
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const body = await res.text();

    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": contentType },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: "Failed to fetch effective trees", details: message },
      { status: 502 },
    );
  }
}
