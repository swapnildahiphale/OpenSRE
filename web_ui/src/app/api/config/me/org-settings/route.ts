import { NextRequest, NextResponse } from "next/server";
import { getConfigServiceBaseUrl, getUpstreamAuthHeaders } from "@/app/api/_utils/upstream";

export async function GET(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me/org-settings", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const res = await fetch(upstreamUrl, {
      method: "GET",
      headers: authHeaders,
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to get org settings", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}

export async function PUT(req: NextRequest) {
  try {
    const baseUrl = getConfigServiceBaseUrl();
    const upstreamUrl = new URL("/api/v1/config/me/org-settings", baseUrl);
    const authHeaders = getUpstreamAuthHeaders(req);

    const body = await req.text();
    const res = await fetch(upstreamUrl, {
      method: "PUT",
      headers: {
        ...authHeaders,
        "content-type": req.headers.get("content-type") || "application/json",
      },
      body,
    });

    const contentType = res.headers.get("content-type") || "application/json";
    const resBody = await res.text();
    return new NextResponse(resBody, { status: res.status, headers: { "content-type": contentType } });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to update org settings", details: err?.message || String(err) },
      { status: 502 },
    );
  }
}
