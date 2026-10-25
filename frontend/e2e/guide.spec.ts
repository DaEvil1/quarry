// The Guide (docs/SPEC.md §15): every walkthrough plays to its end on a fresh sandbox, with "Do it for me" on each
// step, and no step fails to find its place; ending one deletes the sandbox and leaves the writer's worlds alone.
// A walkthrough that has gone stale (a renamed button, a moved panel) fails here.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const sandboxes = async () =>
  ((await (await page.request.get("/api/me")).json()) as { worlds: { slug: string; sandbox: boolean }[] }).worlds.filter((w) => w.sandbox);

for (const id of ["capture", "timeline", "experiments"]) {
  test(`the ${id} walkthrough plays to its end and cleans up`, async () => {
    test.setTimeout(180_000);
    const own = ((await (await page.request.get("/api/me")).json()) as { worlds: { slug: string }[] }).worlds.map((w) => w.slug);
    await page.goto("/guide");
    await page.getByTestId(`guide-tour-${id}`).getByTestId("guide-try").click();
    const guide = page.getByTestId("guide");
    await expect(guide).toBeVisible({ timeout: 30_000 });
    // the sandbox is the world on screen, and the switcher shows only it besides the writer's own
    expect((await sandboxes()).length).toBe(1);

    const finished = guide.getByTestId("guide-finished");
    await expect(async () => {
      if (await finished.isVisible()) return;
      await guide.getByTestId("guide-next").click({ timeout: 1000 }).catch(() => undefined);
      await expect(finished).toBeVisible({ timeout: 700 });
    }).toPass({ timeout: 150_000, intervals: [300] });
    await expect(guide.getByTestId("guide-missed")).toHaveCount(0);

    await guide.getByTestId("guide-end").click();
    await expect(page).toHaveURL(/\/guide$/);
    await expect(page.getByTestId(`guide-tour-${id}`)).toContainText("Seen");
    await expect.poll(async () => (await sandboxes()).length).toBe(0);
    const after = ((await (await page.request.get("/api/me")).json()) as { worlds: { slug: string }[] }).worlds.map((w) => w.slug);
    expect(after.sort()).toEqual(own.sort());
    await expect(page.getByTestId("world-switcher").first()).not.toContainText("guide sandbox");
  });
}
