#!/usr/bin/env node

require("./next-inprocess-worker-shim");

const nextBin = require.resolve("next/dist/bin/next");
const args = process.argv.slice(2);

process.argv = [process.argv[0], nextBin, "build", ...args];
require(nextBin);
