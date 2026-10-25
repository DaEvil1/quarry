// The demo world: loaded from the New world page, it opens with its books, its bible and the companion's findings,
// and it can be deleted again by typing its name. Runs after the phase specs, in the same signed-in browser state.

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

test("load the demo world, look around, delete it", async () => {
  await page.goto("/new-world");
  await page.getByTestId("demo-world").getByRole("button", { name: "Load the demo world" }).click();
  // a whole world is made: give a busy machine a moment
  await expect(page.getByRole("heading", { name: "The Ninefold Delta (demo)" })).toBeVisible({ timeout: 20_000 });
  const W = new URL(page.url()).pathname;

  // the books, with their cast
  await page.locator(".nav").getByRole("link", { name: "The Ferryman's Daughter" }).click();
  await expect(page.getByTestId("chapters")).toContainText("What the River Kept");
  await expect(page.getByTestId("chapters").locator("li", { hasText: "The Crossing" }).getByTestId("cast")).toContainText("Tamsin Vey");

  // chapter 3: where the writer stopped, and what the companion finds
  await page.getByRole("link", { name: "What the River Kept" }).click();
  await expect(page.getByTestId("back-in")).toContainText("Tamsin opens the compass", { timeout: 20_000 });
  await expect(page.getByTestId("editor").locator(".cm-margin")).toContainText("Should Pell already know");
  await page.getByTestId("tab-archivist").click();
  await expect(page.getByTestId("findings-archivist")).toContainText("“Rook” appears 2×");
  await page.getByTestId("tab-connections").click();
  await expect(page.getByTestId("findings-connections")).toContainText("Pell and Brother Cade share a sentence");

  // the checks across the world
  await page.locator(".nav").getByTestId("nav-checks").click();
  await expect(page.getByTestId("check").filter({ hasText: "Oskar Vey is named in “Ash Season”" })).toBeVisible();
  await expect(page.getByTestId("check").filter({ hasText: "never names Ilse Marrow" })).toBeVisible();

  // and away again
  await page.goto(`${W}/settings`);
  const del = page.getByTestId("delete-world");
  await del.getByRole("button", { name: "Delete this world…" }).click();
  await expect(del.getByRole("button", { name: "Delete forever" })).toBeDisabled();
  await del.getByLabel("Type the world's name to delete it").fill("The Ninefold Delta (demo)");
  await del.getByRole("button", { name: "Delete forever" }).click();
  await expect(page).not.toHaveURL(new RegExp(W));
  await expect(page.getByTestId("world-switcher").first()).not.toContainText("Ninefold");
});
