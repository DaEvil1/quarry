// Phase 4: the manuscript and the editor, history, experiments, salvage, and export → restore. Carries on from the
// earlier specs (world "The Grey Shore" with Varren and Old Harbour in its bible, project "First Light").

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const W = "/w/grey-shore";
let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE, acceptDownloads: true });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const editor = () => page.getByTestId("editor").locator(".cm-content");
const status = () => page.getByTestId("save-status");

async function newChapter(title: string) {
  await page.goto(`${W}/p/first-light`);
  await page.getByLabel("New chapter title").fill(title);
  await page.getByRole("button", { name: "Add chapter" }).click();
  await expect(page.getByLabel("Chapter title")).toHaveValue(title);
}

test("write a chapter: autosave, word count, a misspelled name fixed in the editor", async () => {
  await newChapter("Arrival");
  // likely misspellings are underlined while Revising (Drafting, the default, leaves the text unmarked)
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await editor().click();
  await page.keyboard.type("Varen walks down to Old Harbour.");
  await expect(page.getByTestId("word-count")).toHaveText("6 words");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  // names are marked as they are typed: Old Harbour coloured as a place, Varen squiggled
  const miss = page.getByTestId("editor").locator(".cm-near-miss");
  await expect(miss).toHaveText("Varen");
  await expect(page.getByTestId("editor").locator(".cm-name.cm-k-place")).toHaveText("Old Harbour");
  // resting on the squiggle (once typing has paused) offers the fixes
  await miss.hover();
  await page.getByTestId("near-miss-strip").getByRole("button", { name: "Replace with Varren" }).click();
  await expect(editor()).toHaveText("Varren walks down to Old Harbour.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await expect(page.getByTestId("editor").locator(".cm-near-miss")).toHaveCount(0);
});

test("checkpoint with Ctrl+S, write on, and restore from History", async () => {
  await editor().click();
  await page.keyboard.press("Control+s");
  await page.getByLabel("Checkpoint label (optional)").fill("first draft");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Checkpoint “first draft” kept.")).toBeVisible();

  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" The gulls were loud.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });

  await page.getByRole("button", { name: "History" }).click();
  const history = page.getByTestId("history");
  await history.getByRole("button", { name: /first draft/ }).click();
  await expect(history.locator("ins")).toContainText("The gulls were loud.");
  await history.getByRole("button", { name: "Restore this version" }).click();
  await expect(editor()).toHaveText("Varren walks down to Old Harbour.");
  await expect(page.getByText("Restored. The text it replaced is in History.")).toBeVisible();
});

test("point of view, a second chapter, and the order", async () => {
  await page.getByLabel("Point of view").selectOption({ label: "Varren" });
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await newChapter("Storm");
  await editor().click();
  await page.keyboard.type("Rain over the water.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });

  await page.goto(`${W}/p/first-light`);
  const rows = page.getByTestId("chapters").locator(".chapter-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("Arrival");
  await expect(rows.first()).toContainText("Varren");
  await expect(page.getByTestId("pov-tally")).toContainText("Varren");
  await Promise.all([page.waitForResponse((r) => r.url().endsWith("/chapter-order") && r.ok()), page.getByRole("button", { name: "Move Storm up" }).click()]);
  await expect(rows.first()).toContainText("Storm");
  await page.reload();
  await expect(rows.first()).toContainText("Storm");
  await expect(page.getByTestId("manuscript-summary")).toHaveText("2 chapters · 10 words");
});

test("an experiment from scratch, accepted: it takes the old chapter's place", async () => {
  await page.getByTestId("chapters").getByRole("link", { name: "Arrival" }).click();
  await page.getByLabel("Experiment starts from").selectOption("scratch");
  await page.getByRole("button", { name: "Start an experiment" }).click();
  await expect(page.getByTestId("experiment-bar")).toContainText("Rewrite of Arrival");
  // an empty page: only the placeholder shows
  await expect(editor()).toHaveText("Start the rewrite from a blank page…");
  await editor().click();
  await page.keyboard.type("Night, and Varren rows in without lights.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });

  await page.getByTestId("experiment-bar").getByRole("button", { name: "Accept" }).click();
  // the review before the old chapter leaves the book, with its harvest note (docs/SPEC.md §13.6.2)
  await page.getByLabel("Harvest note for Arrival").fill("the harbour walk");
  await page.getByRole("button", { name: "Accept", exact: true }).last().click();
  await expect(page.getByText("Accepted: this draft is now the chapter.")).toBeVisible();
  await expect(page.getByTestId("experiment-bar")).toHaveCount(0);

  await page.goto(`${W}/p/first-light`);
  const rows = page.getByTestId("chapters").locator(".chapter-row");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Arrival");
  await expect(page.getByTestId("manuscript-summary")).toHaveText("2 chapters · 11 words");
});

test("retire a chapter; salvage keeps both, with notes, and searches them", async () => {
  await page.getByTestId("chapters").getByRole("link", { name: "Storm" }).click();
  await page.getByRole("button", { name: "Retire to Salvage" }).click();
  await page.getByLabel("Harvest note for Storm").fill("the rain image");
  await page.getByRole("button", { name: "Retire", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${W}/p/first-light$`));
  await page.getByRole("link", { name: /Salvage/ }).click();
  const entries = page.getByTestId("salvage-entry");
  await expect(entries).toHaveCount(2);
  await expect(entries.filter({ hasText: "Storm" })).toContainText("the rain image");
  await expect(entries.filter({ hasText: "Arrival" })).toContainText("the harbour walk");
  await page.getByLabel("Search").fill("Harbour");
  await expect(entries).toHaveCount(1);
  await expect(entries.locator("mark")).toHaveText("Harbour");
});

test("the bible knows where a name first appears, and lists chapters among the mentions", async () => {
  await page.goto(`${W}/bible`);
  await page.getByRole("link", { name: "Varren" }).click();
  // Storm was retired, so the rewritten Arrival is chapter 1
  await expect(page.getByTestId("first-appearance")).toContainText("Arrival · chapter 1");
  await expect(page.getByTestId("mentions").filter({ hasText: "Night, and Varren rows in" })).toHaveCount(1);
});

test("export the world and restore it as a new one", async () => {
  await page.goto(W);
  const download = page.waitForEvent("download");
  await page.getByTestId("export").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^quarry-grey-shore-\d{4}-\d{2}-\d{2}\.zip$/);
  const path = test.info().outputPath("export.zip");
  await file.saveAs(path);

  await page.goto("/new-world");
  await page.getByLabel("Export zip").setInputFiles(path);
  // a whole world is made: give a busy machine a moment
  await expect(page).toHaveURL(/\/w\/grey-shore-2$/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "The Grey Shore" })).toBeVisible();
  await page.goto("/w/grey-shore-2/p/first-light");
  await expect(page.getByTestId("chapters").locator(".chapter-row")).toHaveCount(1);
  await expect(page.getByTestId("chapters")).toContainText("Arrival");
  await page.goto("/w/grey-shore-2/bible");
  await expect(page.getByTestId("bible-list").first()).toContainText("Varren");
});

test("the editor on a phone", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${W}/p/first-light`);
  await page.getByTestId("chapters").getByRole("link", { name: "Arrival" }).click();
  await expect(editor()).toContainText("Night, and Varren rows in without lights.");
  await expect(page.getByLabel("Point of view")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
