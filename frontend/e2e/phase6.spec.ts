// Phase 6: the world model. Facts and relationships on entries (reading both ways), the bible by kind, and the
// editor: names coloured by kind as they are typed, a card when resting on one (never while typing), and the strip
// that turns a selection into a new entry. Carries on from the earlier specs (world "The Grey Shore" with Varren,
// Isolde and Old Harbour in its bible, project "First Light").

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

const editor = () => page.getByTestId("editor").locator(".cm-content");
const status = () => page.getByTestId("save-status");

async function openEntry(name: string) {
  await page.goto(`${W}/bible`);
  await page.getByTestId("bible-list").getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

test("an entry gets a one-liner, facts and relationships that read both ways", async () => {
  await page.goto(`${W}/bible/k/faction`);
  await expect(page.getByRole("heading", { name: "Factions" })).toBeVisible();
  await page.getByLabel("New entry").fill("Lamp Guild");
  await page.getByRole("button", { name: "Add to the bible" }).click();
  await expect(page.getByRole("heading", { name: "Lamp Guild" })).toBeVisible();
  await expect(page.getByLabel("Kind")).toHaveValue("faction");

  await openEntry("Varren");
  await page.getByTitle("Edit one line").click();
  await page.getByLabel("One line").fill("Keeps the light at Old Harbour");
  await page.keyboard.press("Enter");
  await expect(page.locator(".entry-summary")).toHaveText("Keeps the light at Old Harbour");

  const facts = page.getByTestId("facts");
  await facts.getByLabel("New fact standing").selectOption("canon");
  await facts.getByLabel("New fact label").fill("eye colour");
  await facts.getByLabel("New fact value").fill("grey");
  await facts.getByRole("button", { name: "Add" }).click();
  await expect(facts.locator("table")).toContainText("grey");

  const rel = page.getByTestId("relationships");
  async function relate(to: string, reads: string) {
    await rel.getByLabel("Bible entry").fill(to);
    await page.keyboard.press("Enter");
    await rel.getByLabel("How they\'re connected").selectOption({ label: reads });
    await rel.getByLabel("New relationship standing").selectOption("canon");
    await rel.getByRole("button", { name: "Add", exact: true }).click();
    await expect(rel.locator("dl")).toContainText(to);
  }
  await relate("Isolde", "parent of");
  await relate("Old Harbour", "lives in");
  await relate("Lamp Guild", "member of");
  await expect(rel.locator("dt")).toHaveText(["lives in", "member of", "parent of"]);

  // the other side of each reads backwards
  await rel.getByRole("link", { name: "Isolde" }).click();
  await expect(page.getByRole("heading", { name: "Isolde" })).toBeVisible();
  await expect(page.getByTestId("relationships").locator("dl")).toContainText("child of");
  await expect(page.getByTestId("relationships").locator("dd")).toContainText("Varren");
  await openEntry("Lamp Guild");
  await expect(page.getByTestId("relationships").locator("dt")).toHaveText("has member");
  await openEntry("Old Harbour");
  await expect(page.getByTestId("relationships").locator("dt")).toHaveText("home of");

  // the characters' table carries the one-liner
  await page.goto(`${W}/bible/k/character`);
  await expect(page.getByTestId("bible-list")).toContainText("Keeps the light at Old Harbour");
  await expect(page.getByTestId("nav-kind-faction")).toContainText("1");
});

test("a new kind of relationship, and one in use can't be removed", async () => {
  await page.goto(`${W}/bible/types`);
  await page.getByLabel("From kind").selectOption("character");
  await page.getByLabel("Label", { exact: true }).fill("apprenticed to");
  await page.getByLabel("To kind").selectOption("character");
  await page.getByLabel("Reverse label").fill("master of");
  await page.getByRole("button", { name: "Add" }).click();
  const row = page.getByTestId("relation-types").locator("li", { hasText: "apprenticed to" });
  await expect(row).toContainText("master of");
  await expect(row).toContainText("unused");
  await expect(page.getByTestId("relation-types").locator("li", { hasText: "parent of" }).getByRole("button", { name: /Remove/ })).toBeDisabled();
  await row.getByRole("button", { name: /Remove/ }).click();
  await expect(page.getByTestId("relation-types").locator("li", { hasText: "apprenticed to" })).toHaveCount(0);
});

test("writing: names coloured by kind as they're typed, a card when resting, none while typing", async () => {
  await page.goto(`${W}/p/first-light`);
  await page.getByLabel("New chapter title").fill("Night watch");
  await page.getByRole("button", { name: "Add chapter" }).click();
  await expect(page.getByLabel("Chapter title")).toHaveValue("Night watch");
  await editor().click();
  await page.keyboard.type("Varren lit the lamp for the Lamp Guild. Isolde watched from Old Harbour.");

  const ed = page.getByTestId("editor");
  await expect(ed.locator(".cm-name.cm-k-character")).toHaveText(["Varren", "Isolde"]);
  await expect(ed.locator(".cm-name.cm-k-faction")).toHaveText("Lamp Guild");
  await expect(ed.locator(".cm-name.cm-k-place")).toHaveText("Old Harbour");

  // straight after typing, resting on a name opens nothing
  await ed.locator(".cm-k-faction").hover();
  await page.waitForTimeout(700);
  await expect(page.getByTestId("name-card")).toHaveCount(0);

  // once the writer has paused, it does (resting again if the pointer first arrived inside the quiet moment,
  // which a slow machine can stretch)
  await page.waitForTimeout(600);
  const card = page.getByTestId("name-card");
  await expect(async () => {
    await page.mouse.move(0, 0);
    await ed.locator(".cm-k-character").first().hover({ position: { x: 4, y: 4 } });
    await expect(card).toBeVisible({ timeout: 1500 });
  }).toPass({ timeout: 15_000 });
  await expect(card).toContainText("Keeps the light at Old Harbour");
  await expect(card).toContainText("grey");
  await expect(card).toContainText("Isolde");
  // and typing closes it
  await page.keyboard.type(" ");
  await expect(card).toHaveCount(0);
  await page.keyboard.press("Backspace");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
});

test("a selected word becomes a new entry from the strip", async () => {
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Brannoch");
  const ed = page.getByTestId("editor");
  await page.keyboard.press("Control+Shift+ArrowLeft");
  const strip = page.getByTestId("selection-strip");
  await expect(strip).toBeVisible();
  await strip.getByRole("button", { name: "+ Character" }).click();
  await expect(ed.locator(".cm-name.cm-k-character", { hasText: "Brannoch" })).toBeVisible();
  // the cursor is back after the word, so writing simply carries on
  await page.keyboard.type(" rowed out alone.");
  await expect(editor()).toContainText("Brannoch rowed out alone.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await page.goto(`${W}/bible/k/character`);
  await expect(page.getByTestId("bible-list")).toContainText("Brannoch");
});

test("selecting a name shows its card, and the card links it to another entry", async () => {
  await page.goto(`${W}/p/first-light`);
  await page.getByRole("link", { name: "Night watch" }).click();
  const ed = page.getByTestId("editor");
  await ed.locator(".cm-k-character", { hasText: "Isolde" }).dblclick();
  const card = page.getByTestId("name-card");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Isolde");
  await card.getByRole("button", { name: "Link to…" }).click();
  await page.getByLabel("Link to").fill("Old Harb");
  await page.keyboard.press("Enter");
  await card.getByRole("button", { name: "visits" }).click();
  await expect(card).toContainText("Linked: visits Old Harbour.");

  await openEntry("Isolde");
  const rel = page.getByTestId("relationships");
  await expect(rel.locator("dt")).toContainText(["child of", "visits"]);
  await expect(rel.locator("dd").last()).toContainText("Old Harbour");
});

test("a fact's evidence is noted in place", async () => {
  await openEntry("Varren");
  const row = page.getByTestId("facts").locator("tr", { hasText: "eye colour" });
  await row.hover();
  await row.getByTitle("Edit evidence").click();
  await page.getByLabel("Evidence").fill("his eyes, grey as the harbour");
  await page.keyboard.press("Enter");
  await expect(row).toContainText("his eyes, grey as the harbour");
});

test("writing settings: names uncoloured, then back to defaults", async () => {
  await page.goto("/settings");
  const s = page.getByTestId("writing-settings");
  await s.getByLabel("Colour names by kind").uncheck();
  await page.goto(`${W}/p/first-light`);
  await page.getByRole("link", { name: "Night watch" }).click();
  const ed = page.getByTestId("editor");
  await expect(ed.locator(".cm-name").first()).toBeVisible();
  await expect(ed.locator(".cm-k-character")).toHaveCount(0);
  await page.goto("/settings");
  await s.getByRole("button", { name: "Back to defaults" }).click();
  await expect(s.getByLabel("Colour names by kind")).toBeChecked();
});

test("on a phone the entry page fits", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openEntry("Varren");
  await expect(page.getByTestId("relationships")).toContainText("Isolde");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
