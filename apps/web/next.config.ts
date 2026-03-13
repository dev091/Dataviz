import path from "path";
import type { NextConfig } from "next";

const disableParallelBuild = process.platform === "win32" || process.env.NEXT_DISABLE_PARALLEL_BUILD === "1";
const disableBuildChecks = process.platform === "win32" || process.env.NEXT_DISABLE_BUILD_CHECKS === "1";

const nextConfig: NextConfig = {
  transpilePackages: ["@platform/types"],
  outputFileTracingRoot: path.join(__dirname, "../.."),
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    webpackBuildWorker: !disableParallelBuild,
    parallelServerCompiles: !disableParallelBuild,
    parallelServerBuildTraces: !disableParallelBuild,
  },
  eslint: {
    ignoreDuringBuilds: disableBuildChecks,
  },
  typescript: {
    ignoreBuildErrors: disableBuildChecks,
  },
};

export default nextConfig;
