const { PassThrough } = require("stream");

// Force Next.js jest-worker calls to run in-process for constrained environments
// where spawning child processes is blocked (EPERM).
const jestWorker = require("next/dist/compiled/jest-worker");

class InProcessJestWorker {
  constructor(workerPath, options = {}) {
    this._workerPath = workerPath;
    this._options = options;
    this._workerModule = require(workerPath);
    this._stdout = new PassThrough();
    this._stderr = new PassThrough();
    this._workerPool = { _workers: [] };

    const exposedMethods = Array.isArray(options.exposedMethods) ? options.exposedMethods : [];
    for (const method of exposedMethods) {
      this[method] = async (...args) => {
        const fn = this._workerModule[method];
        if (typeof fn !== "function") {
          throw new Error(`In-process worker method not found: ${method}`);
        }

        const prevIsWorker = process.env.IS_NEXT_WORKER;
        process.env.IS_NEXT_WORKER = "true";
        try {
          return await fn(...args);
        } finally {
          if (prevIsWorker === undefined) {
            delete process.env.IS_NEXT_WORKER;
          } else {
            process.env.IS_NEXT_WORKER = prevIsWorker;
          }
        }
      };
    }
  }

  getStdout() {
    return this._stdout;
  }

  getStderr() {
    return this._stderr;
  }

  end() {
    return Promise.resolve();
  }
}

jestWorker.Worker = InProcessJestWorker;
