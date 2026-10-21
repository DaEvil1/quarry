// Phase 5: the offline copy. On a phone, in airplane mode: open a chapter from the copy on the device, browse its
// snapshots and restore one, keep writing, survive a reload, and have it all reach the server once back online.
// Carries on from the earlier specs (chapter "Arrival" in "First Light").

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

test.describe.configure({ mode: "serial" });

const W = "/w/grey-shore";
let context: BrowserContext;
let page: Page;
let chapterUrl = "";

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 } });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const editor = () => page.getByTestId("editor").locator(".cm-content");
const status = () => page.getByTestId("save-status");

async function checkpoint(label: string) {
  await page.getByRole("button", { name: /Checkpoint/ }).click();
  await page.getByLabel("Checkpoint label (optional)").fill(label);
  await page.keyboard.press("Enter");
  await expect(page.getByText(`Checkpoint “${label}” kept.`)).toBeVisible();
}

test("online: write, keep two checkpoints, sync the offline copy", async () => {
  await page.goto(`${W}/p/first-light`);
  await page.getByTestId("chapters").getByRole("link", { name: "Arrival" }).click();
  await page.waitForURL(/\/chapters\//);
  chapterUrl = page.url();
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" The tide turns.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await checkpoint("phone one");
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Gulls.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await checkpoint("phone two");

  await page.goto("/settings");
  const offline = page.getByTestId("offline-settings");
  await offline.getByRole("button", { name: "Sync now" }).click();
  await expect(offline).toContainText("Synced.");
  await expect(offline).toContainText(/\d+ chapters and \d+ snapshots \(up to the last 30 of each\)/);

  // the app must be installed (the service worker in control) before the network goes away
  await waitForServiceWorker(page);
});

test("airplane mode: the chapter list and the chapter open from the device", async () => {
  await context.setOffline(true);
  await page.goto(`${W}/p/first-light`);
  await expect(page.getByTestId("manuscript-offline")).toBeVisible();
  await page.getByTestId("chapters").getByRole("link", { name: "Arrival" }).click();
  await page.waitForURL(chapterUrl);
});

test("airplane mode: history is there, and a restore works", async () => {
  await page.goto(chapterUrl);
  await expect(page.getByTestId("offline-copy")).toBeVisible();
  await expect(editor()).toContainText("The tide turns. Gulls.");

  await page.getByRole("button", { name: "History" }).click();
  const history = page.getByTestId("history");
  await expect(page.getByTestId("history-offline")).toBeVisible();
  await history.getByRole("button", { name: /phone one/ }).click();
  await expect(history.locator("ins")).toContainText("Gulls.");
  await history.getByRole("button", { name: "Restore this version" }).click();
  await expect(page.getByText("Restored on this device.")).toBeVisible();
  await expect(editor()).toContainText("The tide turns.");
  await expect(editor()).not.toContainText("Gulls.");
});

test("airplane mode: keep writing, close and reopen, nothing is lost", async () => {
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Written on the ferry.");
  await expect(status()).toHaveText(/Offline|Not saved/, { timeout: 15_000 });
  await page.waitForTimeout(600); // the draft is kept on the device a moment after typing
  await page.reload();
  await expect(page.getByText("Text from this device that wasn't saved yet is back in the editor.")).toBeVisible();
  await expect(editor()).toContainText("The tide turns. Written on the ferry.");
});

test("back online: the text saves, and the snapshot of what the restore replaced reaches the server", async () => {
  await context.setOffline(false);
  await expect(status()).toHaveText("Saved", { timeout: 20_000 });
  await page.reload();
  await expect(editor()).toContainText("The tide turns. Written on the ferry.");
  await expect(page.getByTestId("offline-copy")).toHaveCount(0);
  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByTestId("history")).toContainText("Before restoring an older version (offline)", { timeout: 15_000 });
});
