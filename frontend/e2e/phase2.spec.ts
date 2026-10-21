// Phase 2: capture (also offline, also with the app opened offline), sharing into Quarry, keyboard triage with
// decisions and undo, and the inbox on a phone. Carries on from phase1.spec.ts's world "The Grey Shore" with the
// projects "Ebb Tide" and "First Light", signed in through the state it saved.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

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

async function captureText(text: string) {
  await page.getByLabel("What's on your mind?").fill(text);
  await page.getByRole("button", { name: "Save", exact: true }).click();
}

test("capture at the desk, into a project", async () => {
  await page.goto(`${W}/capture`);
  await page.getByRole("radio", { name: "Question" }).click();
  await page.getByRole("radio", { name: "First Light" }).click();
  await page.getByLabel("What's on your mind?").fill("Why does the keeper stay on the island?");
  await page.keyboard.press("Control+Enter");
  await expect(page.getByTestId("capture-status")).toHaveText("Saved.");
  await expect(page.getByLabel("What's on your mind?")).toHaveValue("");
  await expect(page.getByTestId("nav-inbox")).toContainText("1");
  // the choice of kind and project sticks for the next capture
  await expect(page.getByRole("radio", { name: "Question" })).toHaveAttribute("aria-checked", "true");
});

test("capture offline, then it syncs when back online", async () => {
  await context.setOffline(true);
  await page.getByRole("radio", { name: "Spark" }).click();
  await page.getByRole("radio", { name: "Whole world" }).click();
  await captureText("The lighthouse lamp is older than the island.");
  await expect(page.getByTestId("capture-status")).toContainText("Saved on this device");
  await expect(page.getByTestId("offline")).toBeVisible();
  await expect(page.getByTestId("pending")).toContainText("1 waiting to sync");

  await context.setOffline(false);
  await expect(page.getByTestId("pending")).toBeHidden({ timeout: 10_000 });
  await expect(page.getByTestId("offline")).toBeHidden();
  await expect(page.getByTestId("nav-inbox")).toContainText("2");
});

test("the installed app opens and captures with no network at all", async () => {
  // the service worker must be installed and in control before the network goes away. A first install that was
  // interrupted by going offline (the step before) fails, and the next load online starts it again.
  await page.goto(`${W}/capture`);
  await waitForServiceWorker(page);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByLabel("What's on your mind?")).toBeVisible();
  await captureText("Storm scene: told from the boat, not the shore.");
  await expect(page.getByTestId("pending")).toContainText("1 waiting to sync");

  await context.setOffline(false);
  await expect(page.getByTestId("pending")).toBeHidden({ timeout: 10_000 });
});

test("sharing from another app opens capture with the text", async () => {
  await page.goto("/share?title=Tide%20tables&text=Spring%20tides%20twice%20a%20month&url=https%3A%2F%2Fexample.com%2Ftides");
  await expect(page).toHaveURL(new RegExp(`${W}/capture$`));
  await expect(page.getByLabel("What's on your mind?")).toHaveValue(
    "Tide tables\n\nSpring tides twice a month\n\nhttps://example.com/tides",
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByTestId("capture-status")).toHaveText("Saved.");
});

test("triage with the keyboard: accept with a decision, defer, undo, reject, harvest", async () => {
  await page.goto(`${W}/triage`);
  const card = page.getByTestId("triage-item");
  await expect(page.getByTestId("triage-position")).toHaveText("1 of 4");
  // oldest first
  await expect(card).toContainText("Why does the keeper stay");

  await page.keyboard.press("a");
  await page.getByLabel("Decision (optional)").fill("The keeper stays because of a promise.");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Accepted · decision logged" })).toBeVisible();
  await expect(card).toContainText("lighthouse lamp");

  await page.keyboard.press("d");
  await expect(card).toContainText("Storm scene");
  await page.keyboard.press("u");
  await expect(card).toContainText("lighthouse lamp");
  await expect(page.getByTestId("triage-position")).toHaveText("1 of 3");

  // move it to a project with the picker, then reject without a decision
  await page.getByLabel("Project").last().selectOption("ebb-tide");
  await expect(card.locator(".pill").nth(1)).toHaveText("Ebb Tide");
  await page.keyboard.press("r");
  await page.keyboard.press("Enter");
  await expect(card).toContainText("Storm scene");

  await page.keyboard.press("h");
  await page.getByLabel("What's worth keeping? (optional)").fill("the view from the boat");
  await page.keyboard.press("Enter");
  await expect(card).toContainText("Tide tables");

  await page.keyboard.press("d");
  await expect(page.getByRole("heading", { name: "Inbox clear" })).toBeVisible();
  await expect(page.getByTestId("nav-inbox")).not.toContainText(/\d/);
});

test("the decisions log has the decision; a manual one can be added", async () => {
  await page.getByRole("link", { name: "See the decisions log" }).click();
  const list = page.getByTestId("decision-list");
  await expect(list).toContainText("The keeper stays because of a promise.");
  await expect(list).toContainText("from triage");
  await page.getByLabel("New decision").fill("Chapter two is told from the boat.");
  await page.getByRole("button", { name: "Log it" }).click();
  await expect(list.first()).toContainText("Chapter two is told from the boat.");
});

test("on a phone: capture first, then close a deferred item from the inbox", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page).toHaveURL(new RegExp(`${W}/capture$`));
  await expect(page.locator(".tabbar")).toBeVisible();

  await page.locator(".tabbar").getByRole("link", { name: "Inbox" }).click();
  await page.getByRole("tab", { name: /Deferred/ }).click();
  const list = page.getByTestId("inbox-list");
  await list.getByRole("button", { name: /Tide tables/ }).click();
  await list.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Accepted" })).toBeVisible();
  await expect(page.getByText("Nothing deferred.")).toBeVisible();

  await page.getByRole("tab", { name: "Closed" }).click();
  await expect(list.locator(".item")).toHaveCount(4);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
