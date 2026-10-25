// Phase 12a: time on one axis and restructuring (docs/SPEC.md §13.1, §13.6). Runs after phase 1 (name order) in its
// signed-in state, in a world of its own, "The Bell Coast", built through the API so each test starts from known data:
// fifteen short chapters in the book "Bells", 1–13 in year 312, 14 a tale in year −800, 15 with no time.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-bell-coast";
const A = "/api/worlds/the-bell-coast";
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
const about = (n: number, changes: Json) => api("PATCH", `${A}/chapters/${chapter[n]}/about`, changes);

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const facts = () => page.getByTestId("facts");

test("the world for phase 12a", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Bell Coast" });
  await api("POST", `${A}/projects`, { name: "Bells" });
  for (const n of ["Seyla", "Varren", "Isolde"]) await entity(n);
  await entity("Old Harbour", "place");
  for (let n = 1; n <= 15; n++) {
    const ch = await api("POST", `${A}/projects/bells/chapters`, { title: n === 14 ? "The Drowned Bell" : `Chapter ${n}`, body: "Seyla sang to Varren and Isolde at Old Harbour.\n" });
    chapter[n] = ch.id;
  }
  for (let n = 1; n <= 13; n++) await about(n, { time_at: 312 });
  await fact("Seyla", "status", "alive");
  await fact("Seyla", "status", "dead", { from_chapter_id: chapter[9] });
  await relate("Varren", "married to", "Seyla", { from_chapter_id: chapter[3] });
});

test("13.1 done when: the tale is set in place, and Seyla's page reads the clock", async () => {
  // the tale's time and mark, from the manuscript list and the editor's side panel
  await page.goto(`${W}/p/bells`);
  const row = page.getByTestId("chapter-14");
  await row.getByRole("button", { name: /^When The Drowned Bell is set/ }).click();
  await row.getByLabel("Time", { exact: true }).fill("-800");
  await row.getByRole("button", { name: "Set" }).click();
  await expect(row.getByTestId("time-field")).toContainText("year −800");
  // set earlier than the chapter before it, and not marked: a quiet hint, one click to mark it a flashback
  await expect(row.getByTestId("set-earlier")).toBeVisible();
  await page.goto(`${W}/chapters/${chapter[14]}`);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith("/about") && r.ok()), page.getByTestId("told-as-select").selectOption("tale")]);
  await page.goto(`${W}/p/bells`);
  await expect(page.getByTestId("chapter-14").getByTestId("told-as")).toHaveText("tale");
  await expect(page.getByTestId("chapter-14").getByTestId("set-earlier")).toHaveCount(0);
  // 15 has no time: it carries on, muted
  await expect(page.getByTestId("chapter-15").getByTestId("time-field")).toContainText("year 312");

  // no "named after death" in the tale; the selector reads each chapter's time and mark
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "after being recorded dead" })).not.toHaveCount(0);
  await expect(page.getByTestId("check").filter({ hasText: "The Drowned Bell" })).toHaveCount(0);
  await page.goto(`${W}/bible/${ids.Seyla}`);
  const asOf = page.getByTestId("as-of");
  await asOf.selectOption({ label: "14 · The Drowned Bell — tale, year −800" });
  await expect(facts().locator("tr", { hasText: "dead" })).toHaveClass(/off/);
  await expect(facts().locator("tr", { hasText: "alive" })).not.toHaveClass(/off/);
  await expect(page.getByTestId("relationships").getByTestId("relationship").filter({ hasText: "Varren" })).toHaveClass(/off/);
  await asOf.selectOption({ label: "15 · Chapter 15" });
  await expect(facts().locator("tr", { hasText: "dead" })).not.toHaveClass(/off/);
  // removing the tale's time but keeping the mark: still no finding there
  await about(14, { time_at: null });
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "The Drowned Bell" })).toHaveCount(0);
  await about(14, { time_at: -800 });
});

test("13.1.5: born from year 278, chosen with A time…, shows as from year 278; as of a time", async () => {
  await fact("Seyla", "born", "");
  await page.goto(`${W}/bible/${ids.Seyla}`);
  const row = facts().locator("tr", { hasText: "born" });
  await row.locator(".span-text button").click();
  await row.getByLabel("From chapter").selectOption("time");
  await row.getByLabel("From time").fill("278");
  await row.getByRole("button", { name: "Set" }).click();
  await expect(facts().locator("tr", { hasText: "born" }).locator(".span-text")).toHaveText("from year 278");
  // as of a time: year 0 is before her birth
  await page.getByTestId("as-of").selectOption("@time");
  await page.getByTestId("as-of-time").fill("0");
  await page.getByRole("button", { name: "Set", exact: true }).click();
  await expect(page).toHaveURL(/at=0/);
  await expect(facts().locator("tr", { hasText: "born" })).toHaveClass(/off/);
});

test("13.1.8 done when: outside time, on the page as of anything, and no conflict", async () => {
  await fact("Seyla", "title", "Lady of Old Harbour");
  await fact("Seyla", "title", "Queen of the Hollow Court", { outside_time: true });
  for (const q of [`asof=${chapter[2]}`, `asof=${chapter[14]}`, "at=0"]) {
    await page.goto(`${W}/bible/${ids.Seyla}?${q}`);
    const queen = facts().locator("tr", { hasText: "Queen of the Hollow Court" });
    await expect(queen).not.toHaveClass(/off/);
    await expect(queen.locator(".span-text")).toHaveText("outside time");
  }
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "is both" })).toHaveCount(0);
});

test("13.1.4: the where grid in happened order", async () => {
  await page.goto(`${W}/where`);
  await page.getByTestId("where-order").selectOption("happened");
  const heads = page.getByTestId("where-grid").locator("thead .chapter-head .title");
  await expect(heads.first()).toHaveText("The Drowned Bell");
  await expect(page.getByTestId("where-grid").locator("thead .chapter-head").first().getByTestId("head-when")).toHaveText("tale · year −800");
});

test("13.6.1 done when: New beginning over chapters 1–5, a sixth draft, read as if accepted, and accepting", async () => {
  await page.goto(`${W}/p/bells`);
  const words = await page.getByTestId("manuscript-summary").textContent();
  await page.getByRole("button", { name: "Pick chapter 1", exact: true }).click();
  await page.getByRole("button", { name: "Pick chapter 5", exact: true }).click({ modifiers: ["Shift"] });
  await page.getByTestId("start-experiment").click();
  await page.getByLabel("Experiment title").fill("New beginning");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  const exp = page.getByTestId("experiment");
  await expect(exp.getByTestId("draft")).toHaveCount(5);
  await exp.getByLabel("New draft title").fill("A new opening");
  await exp.getByRole("button", { name: "New draft" }).click();
  await expect(exp.getByTestId("draft")).toHaveCount(6);
  await exp.getByRole("button", { name: "Move draft A new opening up" }).click();
  await expect(exp.getByTestId("draft").nth(4)).toContainText("A new opening");
  await expect(page.getByTestId("experiment-row")).toContainText("New beginning · replaces 1–5");
  await expect(page.getByTestId("experiment-row")).toContainText("6 drafts");
  // the book is unchanged
  await expect(page.getByTestId("manuscript-summary")).toHaveText(words!);
  // read as if accepted: the drafts in place of 1–5
  await exp.getByTestId("read-as-if").click();
  await expect(page.getByTestId("read-as-if-line")).toContainText("New beginning");
  const read = page.getByTestId("read-chapter");
  await expect(read).toHaveCount(16);
  await expect(read.nth(4)).toContainText("A new opening");
  await expect(read.nth(6)).toContainText("Chapter 6");
  // accepting: the review, the harvest notes, then six drafts at the start and the five in Salvage
  await page.goto(`${W}/p/bells`);
  await page.getByTestId("experiment-row").click();
  await page.getByTestId("experiment").getByTestId("accept").click();
  const review = page.getByTestId("retire-review");
  await expect(review.getByTestId("review-row").filter({ hasText: "married to" })).toBeVisible();
  await review.getByLabel("Harvest note for Chapter 1").fill("the first line");
  await review.getByTestId("review-confirm").click();
  await expect(page.getByTestId("chapters").locator(".chapter-row:not(.experiment)")).toHaveCount(16);
  await page.goto(`${W}/p/bells/salvage`);
  await expect(page.getByTestId("salvage-entry")).toHaveCount(5);
  await expect(page.getByTestId("salvage-entry").filter({ hasText: "Chapter 1" })).toContainText("the first line");
});

test("13.6.1: New prologue only adds, with no review", async () => {
  await page.goto(`${W}/p/bells`);
  await page.getByRole("button", { name: "Pick chapter 1", exact: true }).click();
  await page.getByTestId("add-before").click();
  await page.getByLabel("Experiment title").fill("New prologue");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByTestId("experiment-row").filter({ hasText: "New prologue" })).toContainText("adds 1 draft before chapter 1");
  await page.getByTestId("experiment").getByTestId("accept").click();
  await expect(page.getByTestId("review-empty")).toBeVisible();
  await page.getByTestId("review-confirm").click();
  await expect(page.getByTestId("chapter-1")).toContainText("New prologue");
  await expect(page.getByTestId("chapters").locator(".chapter-row:not(.experiment)")).toHaveCount(17);
});

test("13.6.2 done when: retiring chapter 9, keep turns into a time, move preselects 8, Undo puts it all back", async () => {
  // chapter 9 is the only one in year 312: the chapters before it are in 311, those after in 313
  const book = (await api("GET", `${A}/projects/bells/chapters`)).chapters as Json[];
  const nine = book.find((c) => c.id === chapter[9])!;
  const eight = book.find((c) => c.id === chapter[8])!;
  const ten = book.find((c) => c.id === chapter[10])!;
  const at9 = book.indexOf(nine);
  for (const [i, c] of book.entries()) if (i !== at9 && c.title !== "The Drowned Bell") await api("PATCH", `${A}/chapters/${c.id}/about`, { time_at: i < at9 ? 311 : 313 });
  const married = ((await api("GET", `${A}/relationships`)) as unknown as Json[]).find((r) => r.label === "married to")!;
  await api("PATCH", `${A}/relationships/${married.id}`, { base_version: married.version, from_chapter_id: null, until_chapter_id: nine.id });
  for (const who of ["Seyla", "Varren"]) await api("PUT", `${A}/chapters/${nine.id}/presence/${ids[who]}`, { place_id: ids["Old Harbour"] });
  await api("POST", `${A}/items`, { kind: "spark", body: "the storm scene", chapter_id: nine.id });

  await page.goto(`${W}/p/bells`);
  const n = book.findIndex((c) => c.id === nine.id) + 1;
  await page.getByRole("button", { name: `Pick chapter ${n}`, exact: true }).click();
  await page.getByTestId("retire-selected").click();
  const review = page.getByTestId("retire-review");
  const dead = review.getByTestId("review-row").filter({ hasText: "status: dead" });
  await expect(dead.getByTestId("keep-text")).toHaveText("from year 312");
  const wed = review.getByTestId("review-row").filter({ hasText: "married to" });
  await wed.getByTestId("review-action").selectOption("move");
  await expect(wed.getByTestId("review-to")).toHaveValue(eight.id);
  await expect(review.getByTestId("review-presence").getByTestId("review-row")).toHaveCount(2);
  await review.getByTestId("review-presence").getByTestId("review-row").first().getByTestId("review-action").selectOption("drop");
  await expect(review.getByTestId("review-link").getByTestId("review-row")).toHaveCount(1);
  await review.getByTestId("review-confirm").click();
  await expect(page.locator(".toast")).toContainText("3 kept, 1 moved, 1 dropped");
  // her page still shows her alive in 8 and dead in 10
  await page.goto(`${W}/bible/${ids.Seyla}?asof=${eight.id}`);
  await expect(facts().locator("tr", { hasText: "dead" })).toHaveClass(/off/);
  await expect(facts().locator("tr", { hasText: "dead" }).locator(".span-text")).toHaveText("from year 312");
  await page.goto(`${W}/bible/${ids.Seyla}?asof=${ten.id}`);
  await expect(facts().locator("tr", { hasText: "dead" })).not.toHaveClass(/off/);
  // Salvage says what the review did; Undo from the toast is tested on the server: retire again, and undo
  await page.goto(`${W}/p/bells/salvage`);
  await expect(page.getByTestId("salvage-entry").filter({ hasText: book[n - 1]!.title }).getByTestId("review-line")).toHaveText("Its review: 3 kept, 1 moved, 1 dropped.");
});

test("13.6.2: with every chapter in the same year, keep warns and starts on move; Undo from the toast", async () => {
  const book = (await api("GET", `${A}/projects/bells/chapters`)).chapters as Json[];
  const three = book.find((c) => c.title === "Chapter 7")!;
  await fact("Isolde", "home", "Old Harbour", { from_chapter_id: three.id });
  await page.goto(`${W}/p/bells`);
  const n = book.findIndex((c) => c.id === three.id) + 1;
  await page.getByRole("button", { name: `Pick chapter ${n}`, exact: true }).click();
  await page.getByTestId("retire-selected").click();
  const row = page.getByTestId("retire-review").getByTestId("review-row").filter({ hasText: "home" });
  await expect(row.getByTestId("review-warn")).toContainText("are all set in year 311");
  await expect(row.getByTestId("review-action")).toHaveValue("move");
  await page.getByTestId("review-confirm").click();
  await page.locator(".toast").getByRole("button", { name: "Undo" }).click();
  await expect(page.getByTestId(`chapter-${n}`)).toContainText("Chapter 7");
});

test("13.6.3 done when: evidence in a retired chapter, re-anchored to the draft where it is now", async () => {
  const ch = await api("POST", `${A}/projects/bells/chapters`, { title: "The Storm", body: "The river kept him.\n" });
  await entity("Oskar");
  await fact("Oskar", "status", "drowned", { evidence: "The river kept him.", established_in_chapter_id: ch.id });
  const exp = await api("POST", `${A}/projects/bells/experiments`, { title: "Storm, again", start: "copy", range: [ch.id] });
  await api("POST", `${A}/chapters/retire`, { ids: [ch.id] });
  await page.goto(`${W}/bible/${ids.Oskar}`);
  const finding = page.getByTestId("evidence-finding");
  await expect(finding).toContainText("rests on a passage in a retired chapter, “The Storm”");
  await finding.getByRole("button", { name: "Re-anchor…" }).click();
  await expect(finding.getByLabel("Re-anchor to")).toHaveValue(exp.drafts[0].id);
  await finding.getByRole("button", { name: "Re-anchor", exact: true }).click();
  await expect(page.getByTestId("evidence-finding")).toHaveCount(0);
});
