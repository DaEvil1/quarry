// Phase 12b: history and the Timeline (docs/SPEC.md §13.2). Runs after phase 1 (name order) in its signed-in state,
// in a world of its own, "The Lamp Coast", built through the API: fifteen short chapters in the book "Lamps", 1–13 in
// year 312, 14 a tale in year −800, 15 with no time; chapter 2 holds the passage where the Lamp Guild's founding is
// told. The 3,000-event budget is measured by frontend/perf/timeline.perf.ts.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-lamp-coast";
const A = "/api/worlds/the-lamp-coast";
let context: BrowserContext;
let page: Page;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};
const chapter: Record<number, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}
const entity = async (name: string, kind = "character") => (ids[name] = (await api("POST", `${A}/entities`, { name, kind })).id);
const fact = (name: string, label: string, value: string, extra: Json = {}) => api("POST", `${A}/entities/${ids[name]}/facts`, { label, value, ...extra });
async function relate(a: string, label: string, b: string, extra: Json = {}) {
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const t = types.find((x) => x.label === label)!;
  return api("POST", `${A}/relationships`, { type_id: t.id, a_id: ids[a], b_id: ids[b], ...extra });
}
async function setEntity(name: string, changes: Json) {
  const { entity: e } = await api("GET", `${A}/entities/${ids[name]}`);
  return api("PATCH", `${A}/entities/${ids[name]}`, { base_version: e.version, ...changes });
}
const about = (n: number, changes: Json) => api("PATCH", `${A}/chapters/${chapter[n]}/about`, changes);

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const PASSAGE = "“In the first year the Lamp Guild was founded, when Seyla and Isolde carried fire up the harbour wall and swore to keep it.”";
const timeline = () => page.getByTestId("timeline");
const mark = (label: string | RegExp) => timeline().locator('[data-testid="mark"]').filter({ has: page.locator("title", { hasText: label }) });
const card = () => page.getByTestId("name-card").first();
async function cardIn(n: number, name: string) {
  await page.goto(`${W}/chapters/${chapter[n]}`);
  await page.getByTestId("editor").locator(".cm-k-character", { hasText: name }).first().dblclick();
  await expect(card()).toBeVisible();
}
const box = async (l: ReturnType<Page["locator"]>) => (await l.first().boundingBox())!;

test("the world for phase 12b", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Lamp Coast" });
  await api("POST", `${A}/projects`, { name: "Lamps" });
  for (const n of ["Seyla", "Varren", "Isolde"]) await entity(n);
  await entity("the Lamp Guild", "faction");
  await entity("Old Harbour", "place");
  for (let n = 1; n <= 15; n++) {
    const body = n === 2 ? `Varren leaned on the rail and began.\n${PASSAGE}` : "Seyla sang to Varren and Isolde at Old Harbour.\nThe lamps were lit along the wall.";
    chapter[n] = (await api("POST", `${A}/projects/lamps/chapters`, { title: n === 14 ? "The Drowned Bell" : `Chapter ${n}`, body })).id;
  }
  for (let n = 1; n <= 13; n++) await about(n, { time_at: 312 });
  await about(14, { time_at: -800, told_as: "tale" });
  await fact("Seyla", "born", "", { from_time: -1000 });
  await relate("Varren", "married to", "Seyla", { from_chapter_id: chapter[3] });
});

test("13.2.3 done when: Record as event from the passage in chapter 2, with its chips, year 0 and Told in", async () => {
  await page.goto(`${W}/chapters/${chapter[2]}`);
  const ed = page.getByTestId("editor");
  await expect(ed.locator(".cm-k-faction")).toBeVisible();
  await ed.locator(".cm-line").nth(1).click({ clickCount: 3, position: { x: 4, y: 6 } });
  const strip = page.getByTestId("passage-strip");
  await expect(strip).toBeVisible();
  await strip.getByRole("button", { name: "Record as event" }).click();
  const form = page.getByTestId("record-form");
  const who = form.getByTestId("record-who");
  // the names in the passage, ticked as taking part; Varren, outside it, is not offered
  for (const n of ["the Lamp Guild", "Seyla", "Isolde"]) await expect(who.getByLabel(n)).toBeChecked();
  await expect(who).not.toContainText("Varren");
  await form.getByLabel("Event").fill("The Founding");
  await form.getByLabel("When").fill("0");
  await form.getByLabel("When").press("Enter");
  await expect(page.getByTestId("toast")).toContainText("Recorded “The Founding” · 3 taking part");
  await page.getByTestId("toast").getByRole("button", { name: "Open" }).click();
  await expect(page.getByRole("heading", { name: "The Founding" })).toBeVisible();
  await expect(page.getByTestId("event-when").getByTestId("time-field")).toContainText("year 0");
  await expect(page.getByTestId("told-in").getByTestId("telling")).toContainText("the Lamp Guild was founded");
  await expect(page.getByTestId("told-in")).toContainText("Chapter 2");
  ids["The Founding"] = page.url().split("/").pop()!;
});

test("13.2.2 done when: happened lists the tale, the Founding and the book's band with folds; told jumps back; History", async () => {
  await page.goto(`${W}/timeline`);
  await expect(timeline()).toBeVisible();
  const tale = mark("14 · The Drowned Bell — tale");
  const founding = mark("The Founding");
  await expect(tale).toBeVisible();
  await expect(founding).toBeVisible();
  await expect(page.getByTestId("book-band")).toBeVisible();
  // in happened order: the tale, the Founding, then the book
  expect((await box(tale)).x).toBeLessThan((await box(founding)).x);
  expect((await box(founding)).x).toBeLessThan((await box(page.getByTestId("book-band"))).x);
  await expect(page.getByTestId("fold").filter({ hasText: "· 800 years ·" })).toBeVisible();
  // the 312 years between the Founding and the book fold too, closer in
  const f = await box(founding);
  await expect(async () => {
    await page.mouse.move(f.x + f.width / 2, f.y + f.height / 2);
    await page.mouse.wheel(0, -400);
    await expect(page.getByTestId("fold").filter({ hasText: "· 312 years ·" })).toBeVisible({ timeout: 300 });
  }).toPass({ timeout: 15_000 });
  await page.getByTestId("fit").click();

  // told: in book order, chapter 14 a jump back to the left of chapter 13
  await page.getByTestId("tab-told").click();
  const at = async (title: string) => Number(await page.getByTestId("told-row").filter({ has: page.getByRole("link", { name: new RegExp(`· ${title}$`) }) }).getByTestId("told-dot").getAttribute("data-at"));
  expect(await at("The Drowned Bell")).toBeLessThan(await at("Chapter 13"));
  await expect(page.getByTestId("told-row").nth(1).getByTestId("told-in-chapter")).toContainText("The Founding");

  // History: before the book only, the tale and the Founding
  await page.getByTestId("tab-history").click();
  await expect(tale).toBeVisible();
  await expect(founding).toBeVisible();
  await expect(page.getByTestId("book-band")).toHaveCount(0);
  await expect(timeline().locator('[data-lane="book"] [data-testid="cluster"]')).toHaveCount(0);
});

test("13.2.3, 13.2.4 done when: Set died here, her lane, her ages, and her page in happened order", async () => {
  await page.goto(`${W}/chapters/${chapter[9]}`);
  const ed = page.getByTestId("editor");
  await expect(ed.locator(".cm-k-character").first()).toBeVisible();
  await ed.click();
  await page.keyboard.press("Control+A");
  const life = page.getByTestId("life-chips").filter({ hasText: "Seyla" });
  await expect(life).toBeVisible();
  await Promise.all([page.waitForResponse((r) => r.url().includes("/facts") && r.request().method() === "POST" && r.ok()), life.getByRole("button", { name: "died here" }).click()]);
  await expect(life).toContainText("Seyla: died here.");

  // her lane: from her birth to chapter 9 (year 312)
  await page.goto(`${W}/timeline?lanes=${ids.Seyla}`);
  const lane = timeline().locator(`[data-lane="${ids.Seyla}"]`);
  const lifeLine = lane.locator('[data-testid="segment"][data-label="Seyla"]');
  await expect(lifeLine).toHaveAttribute("data-from", "-1000");
  await expect(lifeLine).toHaveAttribute("data-to", "312");

  // her card: age 1312 in chapter 5, age 200 in the tale
  await cardIn(5, "Seyla");
  await expect(card()).toContainText("age 1312");
  await cardIn(14, "Seyla");
  await expect(card()).toContainText("age 200");

  // her page: born, the Founding, married from chapter 3, died
  await page.goto(`${W}/bible/${ids.Seyla}`);
  const rows = page.getByTestId("entity-timeline").getByTestId("slice-row");
  await expect(rows.last()).toContainText("died");
  const texts = await rows.allInnerTexts();
  const pos = (re: RegExp) => texts.findIndex((t) => re.test(t));
  expect(pos(/born/)).toBe(0);
  expect(pos(/The Founding/)).toBeGreaterThan(pos(/born/));
  expect(pos(/married to Varren/)).toBeGreaterThan(pos(/The Founding/));
  expect(pos(/died/)).toBeGreaterThan(pos(/married to Varren/));
  await expect(page.getByTestId("life-line")).toContainText("born year −1000");
  // Open in the Timeline: the page with her lane
  await page.getByTestId("open-in-timeline").click();
  await expect(timeline().locator(`[data-lane="${ids.Seyla}"]`)).toBeVisible();
});

test("13.2.6 done when: eras as bands, the era on the manuscript list, cards and clicks, brushing, folding a lane, the overview", async () => {
  // two eras: the Lamp Years from 280 onward, the Long Ebb 290–300 nested in them
  await entity("the Lamp Years", "event");
  await fact("the Lamp Years", "type", "Era");
  await setEntity("the Lamp Years", { time_at: 280 });
  await entity("the Long Ebb", "event");
  await fact("the Long Ebb", "type", "era");
  await setEntity("the Long Ebb", { time_at: 290, time_end: 300 });

  await page.goto(`${W}/timeline`);
  const band = (name: string) => timeline().locator(`[data-testid="era-band"][data-era="${name}"]`);
  await expect(band("the Lamp Years")).toHaveClass(/era-(amber|moss|teal|sky|indigo|plum|rose|rust)/);
  const outer = await box(band("the Lamp Years"));
  const inner = await box(band("the Long Ebb"));
  expect(inner.height).toBeLessThan(outer.height);
  expect(inner.y).toBeGreaterThan(outer.y);
  expect(await band("the Lamp Years").getAttribute("class")).not.toBe(await band("the Long Ebb").getAttribute("class"));

  // resting on an event shows the editor's card for it; clicking opens its page
  const founding = mark("The Founding");
  await expect(async () => {
    await page.mouse.move(0, 0);
    await founding.hover();
    await expect(card()).toBeVisible({ timeout: 1500 });
  }).toPass({ timeout: 10_000 });
  await expect(card()).toContainText("The Founding");
  await founding.click();
  await expect(page).toHaveURL(new RegExp(`/bible/${ids["The Founding"]}`));

  // brushing along the axis marks a span, kept in the address; years 290–312 leave only that span
  await page.goto(`${W}/timeline`);
  const axis = await box(page.getByTestId("axis"));
  await page.mouse.move(axis.x + axis.width * 0.55, axis.y + axis.height / 2);
  await page.mouse.down();
  await page.mouse.move(axis.x + axis.width * 0.75, axis.y + axis.height / 2, { steps: 5 });
  await page.mouse.up();
  await expect(page).toHaveURL(/from=.*&to=|to=.*&from=/);
  await expect(page.getByTestId("in-span")).toBeVisible();
  await page.goto(`${W}/timeline?from=290&to=312`);
  await expect(page.getByTestId("span-line")).toHaveText("year 290–312 · 22 years · the Lamp Years");
  const inSpan = page.getByTestId("in-span");
  await expect(inSpan.getByTestId("span-item").filter({ hasText: "Chapter 1" }).first()).toBeVisible();
  await expect(inSpan).not.toContainText("The Founding");
  await expect(mark("The Founding")).toHaveClass(/dim/);
  // the book's fourteen chapters at year 312 (15 carries on from 13) are one cluster, inside the span
  const chapters = timeline().locator('[data-lane="book"] [data-testid="cluster"]');
  await expect(chapters).toHaveAttribute("data-count", "14");
  await expect(chapters).not.toHaveClass(/dim/);
  await timeline().press("Escape");
  await expect(inSpan).toHaveCount(0);

  // a time on the manuscript list carries its era, in its tint
  await page.goto(`${W}/p/lamps`);
  const t = page.getByTestId(`chapter-1`).getByTestId("time-field");
  await expect(t).toContainText("year 312 · the Lamp Years");
  await expect(t.locator(".era-tint").first()).toBeVisible();

  // collapsing Seyla's lane leaves a line with her counts
  await page.goto(`${W}/timeline?lanes=${ids.Seyla}`);
  await page.getByTestId(`fold-${ids.Seyla}`).click();
  await expect(page).toHaveURL(new RegExp(`fold=${ids.Seyla}`));
  await expect(timeline().locator(`[data-lane="${ids.Seyla}"]`).getByTestId("lane-counts")).toHaveText("Seyla · 1 event · 0 places");
  await page.getByTestId(`fold-${ids.Seyla}`).click();
  await expect(timeline().locator(`[data-lane="${ids.Seyla}"]`).getByTestId("lane-title")).toHaveText("Seyla");

  // dragging the overview's frame pans the Timeline
  await page.goto(`${W}/timeline`);
  await timeline().focus();
  for (let i = 0; i < 4; i++) await page.keyboard.press("+");
  const frame = await box(page.getByTestId("overview-frame"));
  const before = await box(page.getByTestId("book-band"));
  await page.mouse.move(frame.x + frame.width / 2, frame.y + frame.height / 2);
  await page.mouse.down();
  await page.mouse.move(frame.x + frame.width / 2 - 60, frame.y + frame.height / 2, { steps: 6 });
  await page.mouse.up();
  await expect(async () => expect((await box(page.getByTestId("book-band"))).x).toBeGreaterThan(before.x + 20)).toPass({ timeout: 5000 });
});

test("13.2.2: the unplaced tray sets a time, outside time has its strip, and the filters live in the address", async () => {
  await entity("The Lost Charter", "event");
  await entity("The Opening Vision", "event");
  await setEntity("The Opening Vision", { outside_time: true });
  await page.goto(`${W}/timeline`);
  await expect(page.getByTestId("outside-strip")).toContainText("The Opening Vision");
  const tray = page.getByTestId("unplaced");
  await expect(tray).toContainText("The Lost Charter");
  await tray.getByLabel("When The Lost Charter happens").fill("150");
  await tray.getByRole("button", { name: "Set" }).click();
  await expect(tray).toHaveCount(0);
  await expect(mark("The Lost Charter")).toBeVisible();
  // kinds of mark, in the address, and remembered for the next visit
  await page.getByTestId("kind-chapter").uncheck();
  await expect(page).toHaveURL(/kinds=/);
  await expect(timeline().locator('[data-lane="book"] [data-testid="cluster"]')).toHaveCount(0);
  await page.goto(`${W}/timeline`);
  await expect(page.getByTestId("kind-chapter")).not.toBeChecked();
  await page.getByTestId("kind-chapter").check();
  // the nav has the page after Graph
  await expect(page.getByTestId("nav-timeline")).toBeVisible();
});
