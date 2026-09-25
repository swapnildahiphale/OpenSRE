// @ts-nocheck
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Needed for small, production-ready Docker images (see Dockerfile).
  output: "standalone",
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  async rewrites() {
    const base = process.env.CONFIG_SERVICE_URL;
    if (!base) return [];

    // Proxy identity endpoints to the config service (BFF routes handle /api/v1/*).
    return [
      { source: "/api/auth/me", destination: `${base}/api/auth/me` },
      { source: "/api/whoami", destination: `${base}/api/whoami` },
      { source: "/api/config/identity", destination: `${base}/api/config/identity` },
      // Proxy GitHub App OAuth callback to config service
      // GitHub redirects here after app installation
      { source: "/github/callback", destination: `${base}/github/callback` },
      { source: "/github/installations/:path*", destination: `${base}/github/installations/:path*` },
    ];
  },
};

export default nextConfig;
