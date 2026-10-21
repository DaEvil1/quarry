import type { Page } from "@playwright/test";

// Where phase1.spec.ts leaves its signed-in browser state for the spec files after it (they run in name order).
export const STATE_FILE = "test-results/.signed-in.json";


/**
 * Wait until the installed app (the service worker) controls the page, so it can open without a network. A fresh
 * install can take a few seconds on a slow machine, and a page loaded before it finished isn't controlled until
 * it is loaded again.
 */
export async function waitForServiceWorker(page: Page): Promise<void> {
  await page.waitForFunction(async () => !!(await navigator.serviceWorker.getRegistration())?.active, null, {
    timeout: 30_000,
  });
  for (let i = 0; i < 6; i++) {
    await page.reload();
    if (await page.evaluate(() => !!navigator.serviceWorker.controller)) return;
    await page.waitForTimeout(500 * (i + 1));
  }
  throw new Error("The service worker never took control of the page.");
}
