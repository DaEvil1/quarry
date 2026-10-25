import { defineConfig, devices } from "@playwright/test";

// The end-to-end tests drive a running Quarry (the backend serving the built frontend) against an empty database.
// See docs/development.md for how CI and a local run start it. Passkeys come from Chrome's virtual authenticator,
// so the base URL must use the host name "localhost" (WebAuthn allows plain HTTP only there).
//
// phase1.spec.ts is the setup: first run, a world, and the signed-in state the others start from. One worker runs
// the rest in name order, as before; with --workers=N the projects below keep a run safe. CI gives each shard a
// database and server of its own and sets E2E_SHARD, so update.spec.ts needn't wait for the others there.
const chromium = { ...devices["Desktop Chrome"] };
const chain = /\/(phase[2-9]|revising)\.spec\.ts$/;
const demo = /\/(followups-demo|layout|phase13b|sharednames|tour)\.spec\.ts$/;

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
  projects: [
    { name: "setup", testMatch: "phase1.spec.ts", use: chromium },
    // phases 2–9 and revising carry on in phase 1's world, each from the one before: one at a time, in name order
    { name: "chain", testMatch: chain, dependencies: ["setup"], workers: 1, use: chromium },
    // each loads the demo world, under the same name: one at a time
    { name: "demo", testMatch: demo, dependencies: ["setup"], workers: 1, use: chromium },
    // the Guide's walkthroughs, one sandbox at a time (each replaces the last), so one worker; each walkthrough is a
    // test of its own, so --shard can spread them over several runners, each with its own Quarry
    { name: "guide", testMatch: "guide.spec.ts", dependencies: ["setup"], workers: 1, fullyParallel: true, use: chromium },
    // each builds a world of its own
    {
      name: "own",
      testIgnore: [/\/phase1\.spec\.ts$/, chain, demo, /\/guide\.spec\.ts$/, /\/update\.spec\.ts$/],
      dependencies: ["setup"],
      use: chromium,
    },
    // a new sw.js reaches every open page: last, on its own
    {
      name: "update",
      testMatch: "update.spec.ts",
      dependencies: process.env.E2E_SHARD ? ["setup"] : ["chain", "demo", "guide", "own"],
      use: chromium,
    },
  ],
});
