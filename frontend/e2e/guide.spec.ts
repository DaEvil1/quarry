// The Guide (docs/SPEC.md §15): every walkthrough plays to its end on a fresh sandbox, watched at the instant pace
// (no reading pauses, pointer travel or typing a letter at a time, but every step done and waited for), and no step
// fails to find its place. The sandbox stays afterwards until the next walkthrough or Delete, a
// reload can carry on where it was, and the writer's own worlds are left alone. A walkthrough that has gone stale (a
// renamed button, a moved panel) fails here.
//
// With GUIDE_VIDEO=<folder> the walkthroughs are watched at normal speed instead, and each is recorded to
// <folder>/<id>.webm (the "guide videos" workflow; nothing is kept in the repository).

import { mkdirSync, renameSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

const IDS = [
  "back-in",
  "capture",
  "companion",
  "bible",
  "facts",
  "species",
  "timeline",
  "revising",
  "experiments",
  "journal",
  "chart",
  "names",
  "safe",
];
const VIDEO = process.env.GUIDE_VIDEO;

// each test opens its own context and sandbox: one failing doesn't stop the rest (one worker keeps them in order)

type Me = { worlds: { slug: string; sandbox: boolean }[] };
const me = async (page: Page) => (await (await page.request.get("/api/me")).json()) as Me;
const sandboxes = async (page: Page) => (await me(page)).worlds.filter((w) => w.sandbox);

async function open(browser: Browser) {
  const size = { width: 1280, height: 800 };
  const context = await browser.newContext({
    storageState: STATE_FILE,
    viewport: size,
    ...(VIDEO ? { recordVideo: { dir: VIDEO, size } } : {}),
  });
  if (!VIDEO) await context.addInitScript(() => localStorage.setItem("quarry.guide.pace", JSON.stringify("instant")));
  return { context, page: await context.newPage() };
}

for (const id of IDS) {
  test(`the ${id} walkthrough plays to its end`, async ({ browser }) => {
    test.setTimeout(VIDEO ? 15 * 60_000 : 90_000);
    const { context, page } = await open(browser);
    const own = (await me(page)).worlds.filter((w) => !w.sandbox).map((w) => w.slug);
    await page.goto("/guide");
    await page.getByTestId(`guide-tour-${id}`).getByTestId("guide-watch").click();
    const guide = page.getByTestId("guide");
    await expect(guide).toBeVisible({ timeout: 30_000 });
    expect((await sandboxes(page)).length).toBe(1);

    await expect(guide.getByTestId("guide-finished")).toBeVisible({ timeout: VIDEO ? 14 * 60_000 : 80_000 });
    await expect(guide.getByTestId("guide-missed")).toHaveCount(0);

    // closing the walkthrough keeps the sandbox, to look around in
    await guide.getByTestId("guide-end").click();
    await expect(guide).toHaveCount(0);
    expect((await sandboxes(page)).length).toBe(1);
    const after = (await me(page)).worlds.filter((w) => !w.sandbox).map((w) => w.slug);
    expect(after.sort()).toEqual(own.sort());
    await page.goto("/guide");
    await expect(page.getByTestId(`guide-tour-${id}`)).toContainText("Seen");

    const video = page.video();
    await context.close();
    if (VIDEO && video) {
      mkdirSync(VIDEO, { recursive: true });
      renameSync(await video.path(), join(VIDEO, `${id}.webm`));
    }
  });
}

test("a reload carries on where the walkthrough was; Delete removes the sandbox", async ({ browser }) => {
  test.skip(!!VIDEO);
  const { context, page } = await open(browser);
  await page.goto("/guide");
  await page.getByTestId("guide-tour-experiments").getByTestId("guide-try").click();
  const guide = page.getByTestId("guide");
  await expect(guide).toContainText("1 of", { timeout: 30_000 });
  // Next counts once a step is ready: press it until the step moves on
  for (const n of [2, 3]) {
    await expect(async () => {
      await guide.getByTestId("guide-next").click({ timeout: 1000 });
      await expect(guide).toContainText(`${n} of`, { timeout: 1000 });
    }).toPass({ timeout: 20_000 });
  }

  await page.reload();
  await expect(guide).toHaveCount(0);
  // the sandbox is marked as such, and Quarry doesn't reopen in it
  await expect(page.getByTestId("sandbox-notice")).toBeVisible();
  await page.goto("/guide");
  await page.getByTestId("guide-resume").getByRole("button", { name: "Carry on" }).click();
  await expect(guide).toContainText("3 of");
  await guide.getByTestId("guide-end").click();

  await page.goto("/");
  await expect(page).not.toHaveURL(/guide-sandbox/);
  await page.goto("/guide");
  await page.getByTestId("guide-delete-sandbox").click();
  await expect.poll(async () => (await sandboxes(page)).length).toBe(0);
  await expect(page.getByTestId("guide-sandbox")).toHaveCount(0);
  await context.close();
});
