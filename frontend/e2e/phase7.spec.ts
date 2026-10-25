// Phase 7: story time. Facts that hold from a chapter, entry pages "as of" a chapter, cards in the editor as of the
// chapter being written, "is at" from a card, and the Where-everyone-is grid. Carries on from the earlier specs
// (world "The Grey Shore": Varren, Isolde, Old Harbour, Lamp Guild; project "First Light" with chapters "Arrival"
// … "Night watch", the last one naming Varren, Isolde and Old Harbour in one paragraph).

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const W = "/w/grey-shore";
let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

async function openEntry(name: string) {
  await page.goto(`${W}/bible`);
  await page.getByTestId("bible-list").getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

async function openChapter(title: string) {
  await page.goto(`${W}/p/first-light`);
  await page.getByRole("link", { name: title }).click();
  await expect(page.getByLabel("Chapter title")).toHaveValue(title);
}

test("dead from a chapter: the entry page as of the chapter before and the chapter itself", async () => {
  await openEntry("Varren");
  const facts = page.getByTestId("facts");
  for (const value of ["alive", "dead"]) {
    await facts.getByLabel("New fact standing").selectOption("canon");
    await facts.getByLabel("New fact label").fill("status");
    await facts.getByLabel("New fact value").fill(value);
    await facts.getByRole("button", { name: "Add" }).click();
    await expect(facts.locator("table")).toContainText(value);
  }
  const dead = facts.locator("tr", { hasText: "dead" });
  await dead.hover();
  await dead.getByRole("button", { name: "always" }).click();
  await dead.getByLabel("From chapter").selectOption({ label: "Night watch" });
  await dead.getByRole("button", { name: "Set" }).click();
  await expect(dead).toContainText("from Night watch");

  const alive = facts.locator("tr", { hasText: "alive" });
  await page.getByTestId("as-of").selectOption({ label: "Arrival" });
  await expect(alive).not.toHaveClass(/off/);
  await expect(dead).toHaveClass(/off/);
  await page.getByTestId("as-of").selectOption({ label: "Night watch" });
  await expect(alive).toHaveClass(/off/);
  await expect(dead).not.toHaveClass(/off/);
  // the choice is in the address
  await page.reload();
  await expect(page.getByTestId("as-of")).toHaveValue(/.+/);
  await expect(facts.locator("tr", { hasText: "alive" })).toHaveClass(/off/);
});

test("in the editor, a card reads as of its chapter, and records where someone is", async () => {
  await openChapter("Night watch");
  const ed = page.getByTestId("editor");
  await ed.locator(".cm-k-character", { hasText: "Varren" }).first().dblclick();
  let card = page.getByTestId("name-card");
  await expect(card).toContainText("dead");
  await expect(card).not.toContainText("alive");
  await page.keyboard.press("End");

  await ed.locator(".cm-k-character", { hasText: "Isolde" }).first().dblclick();
  card = page.getByTestId("name-card");
  await card.getByRole("button", { name: "Is at…" }).click();
  await page.getByLabel("Is at").fill("Old");
  await page.keyboard.press("Enter");
  await expect(card).toContainText("Isolde is at Old Harbour in this chapter.");
  await expect(page.locator(".chapter-side")).toContainText("at Old Harbour");
});

test("where everyone is: recorded, derived from the paragraph, and set from a cell", async () => {
  await page.locator(".nav").getByTestId("nav-where").click();
  const grid = page.getByTestId("where-grid");
  await expect(grid).toBeVisible();
  const isolde = page.getByTestId("where-Isolde").locator("td[data-chapter='Night watch']");
  await expect(isolde).toHaveClass(/recorded/);
  await expect(isolde).toContainText("Old Harbour");
  const varren = page.getByTestId("where-Varren").locator("td[data-chapter='Night watch']");
  await expect(varren).toHaveClass(/derived/);
  await expect(varren).toContainText("Old Harbour?");

  await varren.getByRole("button").click();
  await varren.getByLabel("Is at").selectOption({ label: "Old Harbour" });
  await expect(varren).toHaveClass(/recorded/);
  await expect(varren).not.toContainText("?");
});
