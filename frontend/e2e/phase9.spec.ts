// Phase 9: the writing companion. Done when, writing a scene with two unconnected characters and a new name, the
// panel offers to record their connection and to add the name, each in one click; and a character recorded dead
// who appears later is listed on Checks. Also: proofreading fixed from the keyboard (Alt+Enter), the classifying
// pass (F8), stashing a thought, margin notes, and the note for next time. Carries on from the earlier specs (Varren
// is dead from "Night watch" and not linked to Brannoch; "Varen" is still a likely misspelling of Varren).

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
const panel = () => page.getByTestId("companion");

test("done when: the panel offers the connection and the new name, each in one click", async () => {
  await page.goto(`${W}/p/first-light`);
  await page.getByLabel("New chapter title").fill("The gate");
  await page.getByRole("button", { name: "Add chapter" }).click();
  await expect(page.getByLabel("Chapter title")).toHaveValue("The gate");
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await editor().click();
  await page.keyboard.type("Varren met Brannoch at the gate, and Mordwen watched them. Later Mordwen left.");

  await panel().getByTestId("tab-connections").click();
  const pair = panel().getByTestId("findings-connections").locator(".finding", { hasText: "Varren and Brannoch share a sentence here." });
  await expect(pair).toBeVisible();
  await pair.getByRole("button", { name: "Record how…" }).click();
  await pair.getByRole("button", { name: "knows", exact: true }).click();
  await expect(panel().getByTestId("findings-connections")).not.toContainText("Varren and Brannoch share a sentence");

  await panel().getByTestId("tab-archivist").click();
  const name = panel().getByTestId("findings-archivist").locator(".finding", { hasText: "“Mordwen” appears 2×" });
  await name.getByRole("button", { name: "+ Character" }).click();
  await expect(page.getByTestId("editor").locator(".cm-k-character", { hasText: "Mordwen" }).first()).toBeVisible();
  await expect(panel().getByTestId("findings-archivist")).not.toContainText("“Mordwen” appears");
});

test("a character recorded dead who appears later is on Checks", async () => {
  await panel().getByTestId("tab-continuity").click();
  await expect(panel().getByTestId("findings-continuity")).toContainText("Varren is named in “The gate”, after being recorded dead from “Night watch”.");

  await page.locator(".nav").getByTestId("nav-checks").click();
  const check = page.getByTestId("check").filter({ hasText: "Varren is named in “The gate”" });
  await expect(check).toBeVisible();
  await check.getByRole("button", { name: "Later" }).click();
  await expect(page.getByTestId("checks-later")).toContainText("Varren is named in “The gate”");
  await page.getByTestId("checks-later").locator("li", { hasText: "The gate" }).getByRole("button", { name: "Intentional" }).click();
  await expect(page.getByTestId("checks-later")).toHaveCount(0);
});

test("proofreading from the keyboard: Alt+Enter on a mark, F8 to the next misspelling", async () => {
  await page.goto(`${W}/p/first-light`);
  await page.getByRole("link", { name: "The gate", exact: true }).click();
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" It was the the end. Varen slept.");
  const mark = page.getByTestId("editor").locator(".cm-find[data-finding='doubled']");
  await expect(mark).toBeVisible();
  await mark.click();
  await page.keyboard.press("Alt+Enter");
  const strip = page.getByTestId("finding-strip");
  await expect(strip).toBeVisible();
  await expect(strip.getByRole("button", { name: "Remove the second “the”" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(editor()).toContainText("It was the end.");
  await expect(mark).toHaveCount(0);

  await page.keyboard.press("Control+Home");
  await page.keyboard.press("F8");
  await expect(page.getByTestId("near-miss-strip")).toBeVisible();
  await expect(page.getByTestId("near-miss-strip").getByRole("button", { name: "Replace with Varren" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("near-miss-strip")).toHaveCount(0);
  await expect(editor()).toBeFocused();
});

test("stash a thought, and a margin note, without leaving the sentence", async () => {
  await page.keyboard.press("Control+End");
  await page.keyboard.press("Control+Shift+S");
  await page.getByLabel("A thought for later (to the inbox, tied to this chapter)").fill("How old is the gate?");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Stashed in the inbox.")).toBeVisible();
  await expect(editor()).toBeFocused();

  // (the count catches up a moment after typing stops)
  await page.waitForTimeout(500);
  const before = await page.getByTestId("word-count").textContent();
  await page.keyboard.type("\n%% make the gate older");
  await expect(page.getByTestId("editor").locator(".cm-margin")).toHaveText("%% make the gate older");
  await page.waitForTimeout(500);
  await expect(page.getByTestId("word-count")).toHaveText(before!);

  await panel().getByTestId("tab-looseEnds").click();
  const loose = panel().getByTestId("findings-looseEnds");
  await expect(loose).toContainText("How old is the gate?");
  await expect(loose).toContainText("make the gate older");
});

test("leaving after writing asks for a note for next time, and coming back shows it", async () => {
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\nThe rain went on for hours and nobody at the gate said a word about the boat, or the lamp, or the long night still ahead of them all.");
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
  await page.locator(".nav").getByRole("link", { name: "Inbox" }).click();
  const ask = page.getByTestId("leave-note");
  await expect(ask).toBeVisible();
  await ask.getByLabel("Before you go: what's next here?").fill("The boat arrives");
  await ask.getByRole("button", { name: "Save and go" }).click();
  await expect(page).toHaveURL(/\/inbox$/);

  await page.goto(`${W}/p/first-light`);
  await page.getByRole("link", { name: "The gate", exact: true }).click();
  const back = page.getByTestId("back-in");
  await expect(back).toContainText("Next: The boat arrives");
  await expect(back).toContainText("ahead of them all");
});
