// A new release while the app is open: the bar says so, and Reload brings the new version in. Runs after the phase
// specs (name order) with their signed-in state. The release is simulated by changing the served sw.js.

import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

const SW = resolve(process.cwd(), "dist/sw.js");

test("a new version shows the update bar, and Reload switches to it", async ({ browser }) => {
  const context = await browser.newContext({ storageState: STATE_FILE });
  const page = await context.newPage();
  const original = readFileSync(SW, "utf-8");
  try {
    await page.goto("/w/grey-shore/capture");
    await waitForServiceWorker(page);
    await expect(page.getByTestId("update-bar")).toHaveCount(0);

    appendFileSync(SW, `\n// release ${Date.now()}\n`);
    await page.evaluate(async () => (await navigator.serviceWorker.getRegistration())?.update());
    await expect(page.getByTestId("update-bar")).toBeVisible({ timeout: 15_000 });

    const before = await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL);
    await page.getByTestId("update-bar").getByRole("button", { name: "Reload" }).click();
    await page.waitForLoadState("load");
    await expect(page.getByTestId("update-bar")).toHaveCount(0);
    await expect
      .poll(() => page.evaluate(async () => (await navigator.serviceWorker.getRegistration())?.waiting === null))
      .toBe(true);
    expect(before).toBeTruthy();
  } finally {
    writeFileSync(SW, original);
    await context.close();
  }
});
