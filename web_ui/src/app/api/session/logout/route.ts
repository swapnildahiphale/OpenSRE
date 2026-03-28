import { NextResponse } from "next/server";

export async function POST() {
  const secure = (process.env.WEB_UI_COOKIE_SECURE || "0").trim() === "1";
  const res = NextResponse.json({ ok: true });
  res.cookies.set({
    name: "opensre_session_token",
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 0,
  });
  return res;
}


