// Phase 10: revising and salvaging (docs/SPEC.md §11). A rename keeps the old name; summaries and statuses on the
// manuscript list; reading one entry's thread (also offline, and together with a second entry); word history; find
// and replace across chapters with Undo; changes since a checkpoint while Revising; and the cuts bin (also offline).
// Runs after the phase specs (name order) and carries on from them: world "The Grey Shore", project "First Light",
// Varren and Isolde in the bible, chapters "Arrival", "Night watch" and "The gate".

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

test.describe.configure({ mode: "serial" });

const W = "/w/grey-shore";
const P = `${W}/p/first-light`;
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
const toast = () => page.getByTestId("toast");

async function openEntry(name: string) {
  await page.goto(`${W}/bible`);
  await page.getByTestId("bible-list").getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

async function openChapter(title: string) {
  await page.goto(P);
  await page.getByTestId("chapters").getByRole("link", { name: title, exact: true }).click();
  await expect(page.getByLabel("Chapter title")).toHaveValue(title);
}

async function rename(to: string) {
  await page.locator("h1.kname").getByRole("button").click();
  await page.getByLabel("Name", { exact: true }).fill(to);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: to })).toBeVisible();
}

test("11.1 done when: a rename keeps the old name, the text still names him, and Remove takes it away", async () => {
  await openEntry("Varren");
  const id = page.url().split("/").pop()!;
  await rename("Varran");
  await expect(toast()).toContainText("Kept “Varren” as another name");
  await expect(page.getByTestId("aliases")).toContainText("Varren");

  // a chapter that says "Varren" still colours it as him
  await openChapter("Night watch");
  await expect(page.getByTestId("editor").locator(`.cm-name[data-entity="${id}"]`, { hasText: "Varren" }).first()).toBeVisible();

  // and back: the name he had a moment ago is kept in turn, and one click on Remove takes it away
  await page.goto(`${W}/bible/${id}`);
  await rename("Varren");
  await expect(toast()).toContainText("Kept “Varran” as another name");
  await expect(page.getByTestId("aliases")).toContainText("Varran");
  await toast().getByRole("button", { name: "Remove" }).click();
  await expect(page.getByTestId("aliases")).not.toContainText("Varran");
  await expect(page.getByTestId("aliases")).not.toContainText("Varren");
});

test("11.2 done when: summaries and statuses on the manuscript list, and renaming a status renames every pill", async () => {
  await page.goto(P);
  const arrival = page.getByTestId("chapters").locator("li", { has: page.getByRole("link", { name: "Arrival", exact: true }) });
  await arrival.getByTestId("chapter-summary").getByRole("button").click();
  await page.getByLabel("Summary of Arrival").fill("Varren rows in at night.");
  await page.keyboard.press("Enter");
  await expect(arrival.getByTestId("chapter-summary")).toHaveText("Varren rows in at night.");

  for (const title of ["Arrival", "Night watch"]) {
    const row = page.getByTestId("chapters").locator("li", { has: page.getByRole("link", { name: title, exact: true }) });
    await row.getByTestId("status-pill").click();
    await row.getByTestId("status-menu").getByRole("menuitem", { name: "rewritten", exact: true }).click();
    await expect(row.getByTestId("status-pill")).toHaveText("rewritten");
  }
  await expect(page.getByTestId("status-tally")).toContainText("2 rewritten");

  await page.getByTestId("statuses").getByRole("button", { name: "rewritten", exact: true }).click();
  await page.getByLabel("Status rewritten").fill("second draft");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("chapters").getByTestId("status-pill").filter({ hasText: "second draft" })).toHaveCount(2);
  await expect(page.getByTestId("status-tally")).toContainText("2 second draft");

  // and in the editor's side panel
  await page.getByTestId("chapters").getByRole("link", { name: "Arrival", exact: true }).click();
  await expect(page.getByTestId("chapter-about")).toContainText("Varren rows in at night.");
  await expect(page.getByLabel("Status", { exact: true })).toHaveValue(/.+/);
});

test("11.4 done when: an entry's thread in story order, offline too, and with a second entry", async () => {
  await openEntry("Varren");
  await page.getByTestId("read-thread").click();
  await expect(page.getByTestId("thread-count")).toHaveText(/^Varren: [1-9]\d* paragraphs? in [1-9]\d* chapters?$/);
  const one = await page.getByTestId("thread-count").textContent();
  await expect(page.getByTestId("thread-para").first()).toContainText("Varren");

  // on the device, with no network
  await waitForServiceWorker(page);
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByTestId("thread-count")).toHaveText(one!);
  await expect(page.getByTestId("thread-offline")).toBeVisible();

  // With… Isolde: only the paragraphs that name both (still offline)
  await page.getByRole("button", { name: "With…" }).click();
  await page.getByPlaceholder("Read together with…").fill("Isol");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("thread-count")).toHaveText(/^Varren and Isolde: \d+ paragraphs? in \d+ chapters?$/);
  for (const p of await page.locator("[data-testid=thread-para]:not(.margin)").all()) {
    await expect(p).toContainText("Isolde");
  }
  await page.getByRole("tab", { name: "Chapters" }).click();
  await expect(page.getByTestId("thread-chapter").first()).toContainText("Isolde");
  await context.setOffline(false);

  // Read together, from their relationship
  await openEntry("Varren");
  await page.getByTestId("relationships").locator(".rel", { hasText: "Isolde" }).getByRole("link", { name: "Read together" }).click();
  await expect(page.getByTestId("thread-count")).toHaveText(/^Varren and Isolde:/);
});

test("11.5 the project page shows the words written and cut", async () => {
  await page.goto(P);
  const chart = page.getByTestId("word-history");
  await expect(chart).toBeVisible();
  await expect(chart.getByTestId("word-total")).toHaveText(/^[\d,]+ words written, [\d,]+ cut\.$/);
  await chart.getByRole("tab", { name: "a year" }).click();
  await expect(chart.getByTestId("word-total")).toHaveText(/words written/);
});

test("11.7 done when: replace previews every hit, unticked ones are left alone, checkpoints in History, Undo puts it back", async () => {
  await page.goto(P);
  await page.getByRole("link", { name: "Find and replace" }).click();
  await page.getByLabel("Find").fill("Varren");
  await page.getByLabel("Replace with").fill("Varran");
  await expect(page.getByTestId("replace-count")).toHaveText(/^\d+ hits in \d+ chapters$/);
  const hits = page.getByTestId("replace-hit");
  const total = await hits.count();
  expect(total).toBeGreaterThanOrEqual(3);
  await expect(hits.first()).toContainText("VarrenVarran");
  // untick two
  await hits.nth(0).getByRole("checkbox").uncheck();
  await hits.nth(1).getByRole("checkbox").uncheck();
  await expect(page.getByTestId("replace-button")).toHaveText(new RegExp(`^Replace ${total - 2} in \\d+ chapters?$`));
  await page.getByTestId("replace-button").click();
  await expect(page.getByTestId("replace-done")).toContainText(`${total - 2} ${total - 2 === 1 ? "hit" : "hits"} replaced`);
  // the two left alone are still there
  await expect(page.getByTestId("replace-count")).toHaveText(/^2 hits in \d chapters?$/);

  // each changed chapter has a checkpoint named for the replace (looked at in another tab: Undo is on this page)
  const other = await context.newPage();
  await other.goto(P);
  for (const title of ["The gate"]) {
    await other.getByTestId("chapters").getByRole("link", { name: title, exact: true }).click();
    await other.getByRole("button", { name: "History" }).click();
    await expect(other.getByTestId("history")).toContainText('Before replacing "Varren" with "Varran"');
    await other.goto(P);
  }
  await other.close();

  // and Undo puts every chapter back
  await page.getByTestId("replace-done").getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("replace-undone")).toContainText("Put back");
  await expect(page.getByTestId("replace-count")).toHaveText(new RegExp(`^${total} hits in`));
});

test("11.6 done when: changes since a labelled checkpoint while Revising, hidden while Drafting, and in the next chapter", async () => {
  await page.goto(P);
  await page.getByRole("button", { name: "Checkpoint every chapter…" }).click();
  await page.getByLabel("Label for a checkpoint of every chapter and experiment").fill("before the polish");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/Checkpoint “before the polish” kept in \d+ chapters/)).toBeVisible();

  await openChapter("Arrival");
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await page.getByLabel("Show changes since").selectOption("before the polish");
  await expect(page.getByTestId("changes-line")).toHaveText("0 words changed, 0 passages removed since “before the polish”");
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Brand new words here.");
  await expect(page.getByTestId("editor").getByTestId("changed").first()).toBeVisible();
  await expect(page.getByTestId("changes-line")).toHaveText("4 words changed, 0 passages removed since “before the polish”");
  // deleted words leave a mark
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("Control+Shift+ArrowRight");
  await page.keyboard.press("Control+Shift+ArrowRight");
  await page.keyboard.press("Backspace");
  await expect(page.getByTestId("editor").getByTestId("removed-mark").first()).toBeVisible();
  await expect(page.getByTestId("changes-line")).toContainText("1 passage removed");

  // Drafting shows nothing
  await page.getByTestId("mode").getByRole("button", { name: "Drafting" }).click();
  await expect(page.getByTestId("editor").getByTestId("changed")).toHaveCount(0);
  await expect(page.getByTestId("editor").getByTestId("removed-mark")).toHaveCount(0);
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await expect(page.getByTestId("editor").getByTestId("changed").first()).toBeVisible();

  // the next chapter shows its changes since the same label
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
  await openChapter("Night watch");
  await expect(page.getByLabel("Show changes since")).toHaveValue("before the polish");
  await expect(page.getByTestId("changes-line")).toHaveText("0 words changed, 0 passages removed since “before the polish”");
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" Later.");
  await expect(page.getByTestId("changes-line")).toHaveText("1 word changed, 0 passages removed since “before the polish”");
  await page.getByLabel("Show changes since").selectOption("");
  await expect(page.getByTestId("editor").getByTestId("changed")).toHaveCount(0);
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
});

test("11.3 done when: Ctrl+Shift+X (also offline) puts a passage in Salvage under Cuts, search finds it, and it goes back where it was", async () => {
  await openChapter("The gate");
  await page.getByTestId("mode").getByRole("button", { name: "Drafting" }).click();
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\nThe heron lifted from the reeds and flew.\nThe end of the gate.");
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
  // select the heron line and cut it
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("End");
  await page.keyboard.press("Shift+Home");
  await page.keyboard.press("Control+Shift+X");
  await expect(toast()).toContainText("Cut 8 words to the bin");
  await expect(editor()).not.toContainText("heron");
  await expect(page.getByTestId("chapter-cuts")).toContainText("The heron lifted from the reeds and flew.");

  // offline: the cut waits on the device and is sent when the connection is back
  await context.setOffline(true);
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.press("Shift+Home");
  await page.keyboard.press("Control+Shift+X");
  await expect(toast()).toContainText("Cut 5 words to the bin");
  await expect(page.getByTestId("chapter-cuts")).toContainText("waiting to sync");
  await context.setOffline(false);
  await expect(page.getByTestId("chapter-cuts")).not.toContainText("waiting to sync", { timeout: 15_000 });
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 20_000 });

  // in Salvage, under Cuts, labelled with the chapter; search finds it
  await page.goto(`${P}/salvage`);
  await page.getByTestId("tab-cuts").click();
  await page.getByLabel("Search").fill("heron");
  const cut = page.getByTestId("cut");
  await expect(cut).toHaveCount(1);
  await expect(cut).toContainText("From The gate");
  await page.getByLabel("Search").fill("end of the gate");
  await expect(page.getByTestId("cut")).toHaveCount(1);

  // put back where it was, from the editor
  await openChapter("The gate");
  const heron = page.getByTestId("chapter-cut").filter({ hasText: "heron" });
  await heron.getByRole("button", { name: "Put back where it was" }).click();
  await expect(editor()).toContainText("The heron lifted from the reeds and flew.");
  const text = await editor().innerText();
  expect(text.indexOf("Varren met Brannoch")).toBeLessThan(text.indexOf("The heron lifted"));
  await expect(page.getByTestId("chapter-cuts")).not.toContainText("heron");
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
});
