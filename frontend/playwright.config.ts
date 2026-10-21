import { defineConfig, devices } from "@playwright/test";

// The end-to-end tests drive a running Quarry (the backend serving the built frontend) against an empty database.
// See docs/development.md for how CI and a local run start it. Passkeys come from Chrome's virtual authenticator,
// so the base URL must use the host name "localhost" (WebAuthn allows plain HTTP only there).
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8767",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
