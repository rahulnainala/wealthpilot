import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Hosted demo: proxy the API under this site's own origin (no CORS, one domain).
  async rewrites() {
    const origin = process.env.API_PROXY_ORIGIN;
    return origin ? [{ source: "/api/:path*", destination: `${origin}/api/:path*` }] : [];
  },
};

export default nextConfig;
