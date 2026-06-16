import { dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Pin the workspace root so Turbopack doesn't infer it from stray lockfiles
  // elsewhere on the machine (e.g. ~/yarn.lock).
  turbopack: {
    root: __dirname,
  },
  env: {
    NEXT_PUBLIC_AGENT_URL:
      process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:8100",
  },
};

export default nextConfig;
