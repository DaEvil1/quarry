import { defineConfig, devices } from "@playwright/test";

// The performance check (perf/): run on its own against a Quarry with an empty database. See docs/development.md.
export default defineConfig({
  testDir: "perf",
  testMatch: "*.perf.ts",
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: process.env.PERF_BASE_URL ?? "http://localhost:8766" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
