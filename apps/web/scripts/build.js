#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const nextBin = require.resolve("next/dist/bin/next");
const args = process.argv.slice(2);
const tsconfigPath = path.join(process.cwd(), "tsconfig.json");
const originalTsconfig = fs.existsSync(tsconfigPath) ? fs.readFileSync(tsconfigPath, "utf8") : null;

function restoreTsconfig() {
  if (originalTsconfig === null || !fs.existsSync(tsconfigPath)) {
    return;
  }
  const current = fs.readFileSync(tsconfigPath, "utf8");
  if (current !== originalTsconfig) {
    fs.writeFileSync(tsconfigPath, originalTsconfig);
  }
}

let direct;
try {
  direct = spawnSync(process.execPath, [nextBin, "build", ...args], {
    stdio: "inherit",
    cwd: process.cwd(),
    env: process.env,
  });
  restoreTsconfig();

  const shouldFallback = Boolean(direct.error) || direct.status !== 0;
  if (!shouldFallback) {
    process.exit(0);
  }

  if (direct.error && direct.error.code && direct.error.code !== "EPERM") {
    throw direct.error;
  }

  require("./next-inprocess-worker-shim");
  process.argv = [process.argv[0], nextBin, "build", ...args];
  require(nextBin);
  restoreTsconfig();
} catch (error) {
  restoreTsconfig();
  throw error;
}