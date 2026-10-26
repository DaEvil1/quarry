// Phase 16: a chapter's plan (docs/SPEC.md §18). Marking a journal entry as a plan and linking it, New plan and Link a
// plan… from the chapter, the plan beside the chapter (tabs, Ctrl+Shift+P, typing autosaves, the divider kept after a
// reload, remembered per chapter), a question from a plan passage ticked for the chapter, a plan before its chapter
// and Start a chapter from it with Undo, the phone's flip, and the split offline. Builds a world of its own.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-plan-coast";
const A = "/api/worlds/the-plan-coast";
let context: BrowserContext;
let page: Page;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}

const side = () => page.getByTestId("plan-side");
const planEditor = () => side().getByTestId("editor").locator(".cm-content");
const chapterEditor = () => page.locator(".chapter-main").first().getByTestId("editor").locator(".cm-content");

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 1600, height: 900 } });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

test("the world for phase 16", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Plan Coast" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  ids.isolde = (await api("POST", `${A}/entities`, { name: "Isolde" })).id;
  for (const [n, t] of [[1, "One"], [2, "Two"], [3, "Three"], [4, "The Quay"], [5, "Five"], [6, "Six"]] as const) {
    ids[`c${n}`] = (await api("POST", `${A}/projects/the-salt-road/chapters`, { title: t, body: `Isolde in ${t}.\n` })).id;
  }
  ids.quay = (await api("POST", `${A}/journal`, { title: "Plan: The Quay", body: "Isolde waits at the quay for the boat.\n\nWho rows her out?\n", entry_date: "2026-10-03", project: "the-salt-road" })).id;
  ids.again = (await api("POST", `${A}/journal`, { title: "The Quay again", body: "Start at night instead.\n", entry_date: "2026-10-14", project: "the-salt-road" })).id;
  ids.flood = (await api("POST", `${A}/journal`, { title: "After the flood", body: "The water goes down.\n", entry_date: "2026-10-20", project: "the-salt-road" })).id;
});

test("18.1 a plan: the switch, Plan for, the Journal's tag and filter; unmarking asks first", async () => {
  await page.goto(`${W}/journal/${ids.quay}`);
  await page.getByTestId("plan-switch").check();
  await expect(page.getByTestId("plan-for")).toContainText("no chapter yet");
  await page.getByTestId("plan-add-chapter").click();
  await page.getByTestId("plan-chapter-picker").getByRole("searchbox").fill("quay");
  await page.getByTestId("plan-chapter-picker").locator(`[data-chapter="${ids.c4}"]`).click();
  await expect(page.getByTestId("plan-for")).toContainText("chapter 4, The Quay");

  await page.goto(`${W}/journal`);
  const quay = page.getByTestId("journal-entry").filter({ hasText: "Plan: The Quay" });
  await expect(quay.getByTestId("plan-tag")).toHaveText("· plan · chapter 4, The Quay");
  await page.getByTestId("plans-filter").getByRole("button", { name: "Plans" }).click();
  await expect(page).toHaveURL(/plans=1/);
  await expect(page.getByTestId("journal-entry")).toHaveCount(1);

  // unmarking a linked plan asks first, unlinks, and Undo brings it back
  await page.goto(`${W}/journal/${ids.quay}`);
  await page.getByTestId("plan-switch").uncheck();
  await expect(page.getByTestId("unmark-plan")).toContainText("This is the plan for chapter 4, The Quay. Unlink it and unmark it?");
  await page.getByTestId("unmark-plan").getByRole("button", { name: "Unlink and unmark" }).click();
  await expect(page.getByTestId("plan-for")).toHaveCount(0);
  await page.getByTestId("toast").getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId("plan-for")).toContainText("chapter 4, The Quay");
});

test("18.1 New plan and Link a plan… from the chapter; a plan for chapters 4 and 5 is listed in both", async () => {
  await api("PUT", `${A}/journal/${ids.quay}/chapters/${ids.c5}`);
  await page.goto(`${W}/chapters/${ids.c5}`);
  await expect(page.getByTestId("chapter-plan")).toHaveCount(1);
  await page.goto(`${W}/chapters/${ids.c4}`);
  await page.getByTestId("link-plan").click();
  await page.getByTestId("plan-picker").locator(`[data-entry="${ids.again}"]`).click();
  // the split opens on it, newest first in the tabs
  await expect(side().getByTestId("plan-tab")).toHaveCount(2);
  await expect(side().getByTestId("plan-tab").first()).toContainText("The Quay again");
  await expect(side().getByTestId("plan-tab").first()).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("chapter-plan")).toHaveCount(0); // the panel folds while the split is open
});

test("18.2 the plan beside the chapter: half each, Ctrl+Shift+P, typing autosaves, the divider and the split remembered", async () => {
  await page.goto(`${W}/chapters/${ids.c4}`);
  await expect(side()).toBeVisible();
  await side().locator(`[data-testid=plan-tab][data-plan="${ids.quay}"]`).click();
  await expect(planEditor()).toContainText("Isolde waits at the quay");
  // names coloured in the plan
  await expect(side().locator(".cm-name", { hasText: "Isolde" }).first()).toBeVisible();
  const chapterBox = await page.locator(".chapter-main").first().boundingBox();
  expect(chapterBox!.width).toBeGreaterThan(500);
  expect(chapterBox!.width).toBeLessThan(900);

  await chapterEditor().click();
  await page.keyboard.press("Control+Shift+P");
  await expect(planEditor()).toBeFocused();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("A new line in the plan.");
  await page.keyboard.press("Control+Shift+P");
  await expect(chapterEditor()).toBeFocused();
  await expect(side().getByTestId("plan-save-status")).toHaveText("Saved", { timeout: 15_000 });
  expect((await api("GET", `${A}/journal/${ids.quay}`)).body).toContain("A new line in the plan.");

  // drag the divider; it keeps its place after a reload, and the chapter opens with its split on the same plan
  const divider = page.getByTestId("plan-divider");
  const d = (await divider.boundingBox())!;
  await page.mouse.move(d.x + 3, d.y + 200);
  await page.mouse.down();
  await page.mouse.move(d.x - 300, d.y + 200, { steps: 5 });
  await page.mouse.up();
  const narrowed = (await page.locator(".chapter-main").first().boundingBox())!.width;
  expect(narrowed).toBeLessThan(chapterBox!.width - 150);
  await page.reload();
  await expect(side()).toBeVisible();
  await expect(side().locator(`[data-testid=plan-tab][data-plan="${ids.quay}"]`)).toHaveAttribute("aria-selected", "true");
  expect(Math.abs((await page.locator(".chapter-main").first().boundingBox())!.width - narrowed)).toBeLessThan(20);
  await divider.dblclick();
  await page.getByTestId("close-plan").click();
  await expect(side()).toHaveCount(0);
});

test("18.4 a question from a plan passage, ticked for the chapter beside, is in its Loose ends", async () => {
  await page.goto(`${W}/chapters/${ids.c4}?plan=${ids.quay}`);
  await expect(planEditor()).toContainText("Who rows her out?");
  await side().getByTestId("editor").locator(".cm-line", { hasText: "Who rows her out?" }).click({ clickCount: 3 });
  await page.locator("[data-testid=passage-strip], [data-testid=selection-strip]").getByRole("button", { name: "Question" }).click();
  const chips = page.getByTestId("item-chapters");
  await expect(chips).toContainText("chapter 4, The Quay");
  await expect(chips.locator("input")).toBeChecked();
  await page.getByTestId("item-form").getByRole("button", { name: "Save" }).click();
  await expect.poll(async () => (await api("GET", `${A}/chapters/${ids.c4}/items`)).some((i: Json) => String(i.body).includes("Who rows her out?"))).toBe(true);
});

test("18.3 a plan before its chapter: Start a chapter from it after chapter 6, then Undo", async () => {
  await api("PATCH", `${A}/journal/${ids.flood}/about`, { is_plan: true });
  await page.goto(`${W}/p/the-salt-road`);
  const waiting = page.getByTestId("plans-waiting");
  await expect(waiting.getByTestId("waiting-plan")).toHaveCount(1);
  await expect(waiting).toContainText("After the flood");
  await expect(page.getByTestId("chapter-4").getByTestId("chapter-plans")).toHaveText("2 plans");
  await waiting.getByTestId("start-chapter").click();
  await waiting.getByTestId("start-where").selectOption({ label: "after chapter 6, Six" });
  await waiting.getByTestId("start-confirm").click();
  await expect(page).toHaveURL(new RegExp(`${W}/chapters/`));
  await expect(side()).toBeVisible();
  await expect(planEditor()).toContainText("The water goes down.");
  await expect(page.getByRole("textbox", { name: "Chapter title" })).toHaveValue("After the flood");
  await expect(page.getByTestId("toast").filter({ hasText: "Chapter 7, After the flood · from its plan" })).toBeVisible();
  await page.getByTestId("toast").filter({ hasText: "from its plan" }).getByRole("button", { name: "Undo" }).click();
  await expect(page).toHaveURL(new RegExp(`${W}/p/the-salt-road`));
  await expect(page.getByTestId("plans-waiting").getByTestId("waiting-plan")).toHaveCount(1);
});

test("18.2 on the phone, Plan flips to the plan and back", async ({ browser }) => {
  const phone = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  await p.goto(`${W}/chapters/${ids.c4}`);
  await expect(p.getByTestId("editor").locator(".cm-content")).toContainText("Isolde in The Quay");
  await p.getByTestId("plan-button").click();
  await expect(p.getByTestId("plan-side")).toBeVisible();
  await expect(p.locator(".chapter-main").first()).toBeHidden();
  await p.getByTestId("flip-back").click();
  await expect(p.locator(".chapter-main").first()).toBeVisible();
  await expect(p.getByTestId("plan-side")).toHaveCount(0);
  await phone.close();
});

test("18.2 offline: the split opens and takes typing", async () => {
  await page.goto("/settings");
  await waitForServiceWorker(page);
  await page.goto("/settings");
  await page.getByTestId("offline-settings").getByRole("button", { name: "Sync now" }).click();
  await expect(page.getByTestId("offline-settings")).toContainText("Synced.");
  await page.goto(`${W}/chapters/${ids.c4}`);
  await expect(page.getByTestId("plan-button")).toBeVisible();
  await context.setOffline(true);
  try {
    await page.reload();
    await expect(chapterEditor()).toContainText("Isolde in The Quay");
    // left open on the plan last time (the question above was made in it): it comes back so, offline too
    await expect(page.getByTestId("plan-button")).toHaveAttribute("aria-pressed", "true");
    await expect(planEditor()).toContainText("Isolde waits at the quay", { timeout: 15_000 });
    await planEditor().click();
    await page.keyboard.type(" Offline words.");
    await expect(planEditor()).toContainText("Offline words.");
  } finally {
    await context.setOffline(false);
  }
});
