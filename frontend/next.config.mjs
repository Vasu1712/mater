/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_AGENT_URL:
      process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:8100",
  },
};

export default nextConfig;
