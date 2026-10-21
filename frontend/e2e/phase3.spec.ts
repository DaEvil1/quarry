// Phase 3: the bible, tags, the name checker's fixes, mentions across items, journal and bible pages. Carries on
// from phase1/phase2 (world "The Grey Shore", signed in through the saved state).

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

async function addEntry(name: string, kind = "character") {
  await page.goto(`${W}/bible`);
  await page.getByLabel("New entry").fill(name);
  await page.getByLabel("Kind").first().selectOption(kind);
  await page.getByRole("button", { name: "Add to the bible" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

async function capture(text: string, tag?: string) {
  await page.goto(`${W}/capture`);
  await page.getByRole("radio", { name: "Whole world" }).click();
  await page.getByLabel("What's on your mind?").fill(text);
  if (tag) {
    await page.getByRole("button", { name: "+ Tag" }).click();
    await page.getByLabel("Bible entry").fill(tag.slice(0, 3));
    await page.keyboard.press("Enter");
    await expect(page.locator(".chip.tag")).toContainText(tag);
  }
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByTestId("capture-status")).toHaveText("Saved.");
}

test("build the bible: entries, another spelling, notes", async () => {
  await addEntry("Old Harbour", "place");
  await addEntry("Isolde");
  await addEntry("Varren");
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Other spellings and names").fill("the Grey Keeper");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByLabel("Notes").fill("Keeper of the light at Old Harbour.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Also: the Grey Keeper")).toBeVisible();

  await page.goto(`${W}/bible`);
  await expect(page.getByTestId("bible-list").first()).toContainText("Isolde");
  await page.getByLabel("Search").fill("grey");
  await expect(page.getByTestId("bible-list")).toHaveCount(1);
  await expect(page.getByTestId("bible-list")).toContainText("Varren");
});

test("capture with a tag, then fix a misspelled name from the inbox", async () => {
  await capture("Varen sails past Old Harbour at dawn.", "Varren");
  await page.goto(`${W}/inbox`);
  await page.getByTestId("inbox-list").getByRole("button", { name: /Varen sails/ }).click();
  const body = page.locator(".item.open");
  await expect(body.locator(".chip.tag")).toContainText("Varren");
  await expect(body.locator(".mention")).toHaveText("Old Harbour");

  await body.locator("button.near-miss").click();
  await page.getByRole("menuitem", { name: "Replace with Varren" }).click();
  await expect(body.locator(".item-text")).toContainText("Varren sails past Old Harbour at dawn.");
  await expect(body.locator("button.near-miss")).toHaveCount(0);
  await expect(body.locator(".mention").first()).toHaveText("Varren");
});

test("the name check finds a misspelling across an item and the journal; fixed as another spelling", async () => {
  await capture("Isolda waits on the pier. Quietly, Tomasz watches.");
  await page.goto(`${W}/journal`);
  await page.getByRole("button", { name: "New entry" }).click();
  await page.getByLabel("Title").fill("What now?");
  await page.getByLabel("Entry").fill("Does Isolda know what the Grey Keeper saw?");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("journal-entry").first()).toContainText("What now?");

  await page.goto(`${W}/names`);
  await expect(page.getByTestId("nav-names")).toContainText("1");
  const group = page.getByTestId("near-miss-group");
  await expect(group).toHaveCount(1);
  await expect(group).toContainText("Isolda");
  await expect(group).toContainText("Isolde");
  await expect(group.locator(".snippet")).toHaveCount(2);
  await group.getByRole("button", { name: "It's another spelling" }).click();
  await expect(page.getByText("No likely misspellings")).toBeVisible();
  await expect(page.getByTestId("nav-names")).not.toContainText(/\d/);
});

test("an entry's page: mentions everywhere, untagged items, tagging from there", async () => {
  await capture("Why does Varren never leave the island?");
  await page.goto(`${W}/bible`);
  await page.getByRole("link", { name: "Varren" }).click();
  const mentions = page.getByTestId("mentions");
  await expect(mentions).toContainText("Varren sails past Old Harbour");
  await expect(mentions).toContainText("What now?");
  await expect(page.getByTestId("unlinked")).toContainText("Why does Varren never leave");
  await page.getByTestId("unlinked").getByRole("button", { name: "Tag" }).click();
  await expect(page.getByText("Tagged.")).toBeVisible();
  await expect(page.getByTestId("unlinked")).toHaveCount(0);

  // the place is mentioned in Varren's own notes
  await page.goto(`${W}/bible`);
  await page.getByRole("link", { name: "Old Harbour" }).click();
  await expect(page.getByTestId("mentions")).toContainText("Varren");
  // and Isolde gained a spelling, which now counts
  await page.goto(`${W}/bible`);
  await page.getByRole("link", { name: "Isolde" }).click();
  await expect(page.getByText("Also: Isolda")).toBeVisible();
  await expect(page.getByTestId("mentions")).toContainText("Isolda waits on the pier");
});

test("triage: tag with l", async () => {
  await page.goto(`${W}/triage`);
  const card = page.getByTestId("triage-item");
  await expect(card).toContainText("Varren sails");
  await page.keyboard.press("j");
  await expect(card).toContainText("Isolda waits");
  await page.keyboard.press("l");
  await page.getByLabel("Bible entry").fill("Iso");
  await page.keyboard.press("Enter");
  await expect(card.locator(".chip.tag")).toContainText("Isolde");
});

test("on a phone the bible has its own tab", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${W}/capture`);
  await page.locator(".tabbar").getByRole("link", { name: "Bible" }).click();
  await expect(page.getByRole("heading", { name: "Bible" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
