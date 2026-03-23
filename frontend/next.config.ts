import type { NextConfig } from "next";

const backendApiBaseUrl =
  process.env.BACKEND_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
