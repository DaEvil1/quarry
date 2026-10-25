// Phase 13b: getting back in and checking (docs/SPEC.md §14.4–§14.9). The front page on the demo world, the note for
// next time in the Journal, "since this was written", Include planned, cause arrows on the Timeline, an entry of more
// than one kind, and the focus per world. Runs after phase 1 (name order) in its signed-in state; the demo world it
// loads is deleted at the end, and the rest is a world of its own built through the API.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-wars-coast";
const A = "/api/worlds/the-wars-coast";
let context: BrowserContext;
let page: Page;
let demo = "";

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};
const chapter: Record<number, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}
const entity = async (name: string, kind = "character", extra: Json = {}) => (ids[name] = (await api("POST", `${A}/entities`, { name, kind, ...extra })).id);
async function relate(a: string, label: string, b: string, extra: Json = {}) {
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const t = types.find((x) => x.label === label)!;
  return api("POST", `${A}/relationships`, { type_id: t.id, a_id: ids[a], b_id: ids[b], ...extra });
}
async function when(name: string, at: number) {
  const { entity: e } = await api("GET", `${A}/entities/${ids[name]}`);
  await api("PATCH", `${A}/entities/${ids[name]}`, { base_version: e.version, time_at: at });
}

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  if (demo) await api("DELETE", `/api/worlds/${demo}`, { name: "The Ninefold Delta (demo)" }).catch(() => undefined);
  await context.close();
});

const nav = () => page.locator(".nav nav");
const navOrder = () => nav().locator("a").evaluateAll((as) => as.map((a) => a.textContent?.trim() ?? ""));

test("14.4 done when: the demo world's front page, with a premise, where you left off, lately, decisions and questions", async () => {
  await page.goto("/");
  demo = (await api("POST", "/api/worlds/demo")).slug;
  await page.goto(`/w/${demo}`);
  await expect(page.getByRole("heading", { name: "The Ninefold Delta (demo)" })).toBeVisible();
  // the premise, edited in place
  await expect(page.getByTestId("premise")).toContainText("A ferry-girl");
  await page.getByTestId("premise").getByRole("button").click();
  await page.getByLabel("Premise").fill("A ferry-girl and a delta of nine channels.");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("premise")).toContainText("A ferry-girl and a delta of nine channels.");
  // where you left off: the latest note, with Continue
  const left = page.getByTestId("left-off");
  await expect(left).toContainText("Continue");
  // the older notes fold under the latest
  await left.getByRole("button", { name: "1 more" }).click();
  await expect(left).toContainText("Settle Hesper's age");
  await expect(left).toContainText("the Journal");
  // lately: days, each dated and with how long ago
  const days = page.getByTestId("lately-day");
  await expect(days.first()).toContainText(/today|yesterday|days ago/);
  await expect(page.getByTestId("lately")).toContainText("words in The Ferryman's Daughter");
  await expect(page.getByTestId("lately")).toContainText("journal entr");
  await expect(page.getByTestId("lately")).toContainText("facts recorded");
  await expect(page.getByTestId("lately")).toContainText("captured");
  await expect(page.getByTestId("latest-decisions")).toContainText("Oskar dies in chapter 2");
  await expect(page.getByTestId("open-questions")).toContainText("Does Pell know who Rook is afraid of?");
  await expect(page.getByTestId("unsure-count")).toContainText("?? in the Journal");
  // Rename, the time unit and Delete are on World settings
  await page.getByTestId("world-settings").click();
  await expect(page.getByRole("heading", { name: "World settings" })).toBeVisible();
  await expect(page.getByTestId("time-unit")).toBeVisible();
  await expect(page.getByTestId("delete-world")).toBeVisible();
  await expect(page.getByRole("button", { name: "Rename" })).toBeVisible();
  // Continue opens the journal entry at the place
  await page.goto(`/w/${demo}`);
  await page.getByTestId("continue").click();
  await expect(page).toHaveURL(/\/(journal|chapters)\/[0-9a-f-]{36}\?at=\d+/);
});

test("14.4 done when: leaving a journal entry after 30 words asks for a note, which then leads where you left off", async () => {
  await page.goto(`/w/${demo}/journal`);
  await page.getByTestId("journal-entry").filter({ hasText: "What the Wardens want" }).getByRole("link").first().click();
  await page.getByTestId("editor").locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" " + Array.from({ length: 32 }, (_, i) => `word${i}`).join(" "));
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 10_000 });
  await page.locator(".nav").getByRole("link", { name: "Overview" }).click();
  const ask = page.getByTestId("leave-note");
  await expect(ask).toBeVisible();
  await ask.getByLabel("Before you go: what's next here?").fill("The first toll, in lanterns");
  await ask.getByRole("button", { name: "Save and go" }).click();
  await expect(page.getByTestId("left-off")).toContainText("The first toll, in lanterns", { timeout: 10_000 });
  await expect(page.getByTestId("left-off")).toContainText("What the Wardens want");
});

test("14.5 done when: an old entry says what happened since, dimmed on the list; one written today says nothing", async () => {
  await page.goto(`/w/${demo}/journal`);
  const old = page.getByTestId("journal-entry").filter({ hasText: "The first map" });
  await expect(old.getByTestId("since-count")).toContainText("since");
  await old.getByRole("link").first().click();
  const since = page.getByTestId("since-this");
  await expect(since).toContainText(/\d+ decisions? and \d+ changes? touch/);
  await since.getByRole("button").click();
  await expect(since).toContainText("Hesper Quill");
  await page.goto(`/w/${demo}/journal`);
  await page.getByTestId("new-entry").click();
  await expect(page.getByTestId("journal-side")).toBeVisible();
  await expect(page.getByTestId("since-this")).toHaveCount(0);
});

test("14.9 done when: Planning reorders the nav, turns Include planned on, opens the world on its front page; Writing back", async () => {
  // under Writing: the projects first
  await page.goto(`/w/${demo}/chapters/${(await api("GET", `/api/worlds/${demo}/projects/the-ferrymans-daughter/chapters`)).chapters[2].id}`);
  await expect(page.getByTestId("editor")).toBeVisible();
  let order = await navOrder();
  expect(order.findIndex((t) => t.startsWith("The Ferryman's Daughter"))).toBeLessThan(order.findIndex((t) => t.startsWith("Capture")));
  await page.goto(`/w/${demo}`);
  await page.locator("main").getByTestId("focus-switch").getByRole("button", { name: "Planning" }).click();
  await expect(async () => {
    order = await navOrder();
    expect(order.indexOf("Journal")).toBeLessThan(order.indexOf("Capture"));
    expect(order.indexOf("Timeline")).toBe(order.indexOf("Decisions") + 1);
    expect(order.findIndex((t) => t.startsWith("The Ferryman's Daughter"))).toBeGreaterThan(order.indexOf("Name check"));
  }).toPass({ timeout: 5000 });
  // Include planned starts on under Planning: Brother Cade's planned death is a finding
  await page.goto(`/w/${demo}/checks`);
  await expect(page.getByTestId("include-planned")).toBeChecked();
  await expect(page.getByTestId("check").filter({ hasText: "Brother Cade is named in “Ash Season”, but is planned dead" }).getByTestId("planned-tag")).toBeVisible();
  // opening the world again lands on its front page; the phone shows Planning too
  await page.goto("/");
  await expect(page).toHaveURL(new RegExp(`/w/${demo}$`));
  const phone = await context.browser()!.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  await p.goto(`/w/${demo}`);
  await expect(p.locator("main").getByTestId("focus-switch").getByRole("button", { name: "Planning" })).toHaveAttribute("aria-pressed", "true");
  await phone.close();
  // back to Writing: the projects first, Include planned off, and the world opens at the last chapter used
  await page.locator("main").getByTestId("focus-switch").getByRole("button", { name: "Writing" }).click();
  await expect(async () => {
    order = await navOrder();
    expect(order.findIndex((t) => t.startsWith("The Ferryman's Daughter"))).toBeLessThan(order.indexOf("Capture"));
  }).toPass({ timeout: 5000 });
  await page.goto(`/w/${demo}/checks`);
  await expect(page.getByTestId("include-planned")).not.toBeChecked();
  await expect(page.getByTestId("check").filter({ hasText: "but is planned dead" })).toHaveCount(0);
  await page.getByTestId("world-switcher").first().click();
  await page.locator(".switcher-menu").first().getByRole("menuitem", { name: "The Ninefold Delta (demo)" }).click();
  await expect(page).toHaveURL(/\/checks$/);
});

test("the world for 13b's checks, arrows and kinds", async () => {
  await api("POST", "/api/worlds", { name: "The Wars Coast" });
  await api("POST", `${A}/projects`, { name: "Lamps" });
  await entity("Seyla");
  for (let n = 1; n <= 12; n++) {
    chapter[n] = (await api("POST", `${A}/projects/lamps/chapters`, { title: `Chapter ${n}`, body: n === 12 ? "Seyla sings at Old Harbour." : "Rain on the harbour." })).id;
  }
  await api("POST", `${A}/entities/${ids.Seyla}/facts`, { label: "status", value: "dead", standing: "planned", from_chapter_id: chapter[9] });
  for (const e of ["The Founding", "The Lamp Wars", "The Burning of the Quay"]) await entity(e, "event");
  await when("The Founding", 0);
  await when("The Lamp Wars", 40);
  await when("The Burning of the Quay", 900);
  await relate("The Founding", "caused", "The Lamp Wars");
  await relate("The Burning of the Quay", "followed from", "The Lamp Wars", { standing: "planned" });
  await entity("Ashgard", "place");
  await entity("Old Harbour", "place");
  await entity("the Lamp Guild", "faction");
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const inside = types.find((t) => t.a_kind === "place" && t.b_kind === "place" && ["in", "inside", "part of"].includes(t.label))!;
  await api("POST", `${A}/relationships`, { type_id: inside.id, a_id: ids["Old Harbour"], b_id: ids.Ashgard });
});

test("14.6 done when: Seyla's planned death is a finding only with Include planned, tagged planned", async () => {
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("include-planned")).not.toBeChecked();
  await expect(page.getByTestId("check").filter({ hasText: "Seyla" })).toHaveCount(0);
  await page.getByTestId("include-planned").check();
  const f = page.getByTestId("check").filter({ hasText: "Seyla is named in “Chapter 12”, but is planned dead from “Chapter 9”." });
  await expect(f).toBeVisible();
  await expect(f.getByTestId("planned-tag")).toBeVisible();
  // in the editor's Continuity tab too
  await page.goto(`${W}/chapters/${chapter[12]}`);
  await page.getByTestId("tab-continuity").click();
  await expect(page.getByTestId("findings-continuity").getByTestId("include-planned")).toBeChecked();
  await expect(page.getByTestId("findings-continuity")).toContainText("planned dead");
  await page.goto(`${W}/checks`);
  await page.getByTestId("include-planned").uncheck();
});

test("14.7 done when: resting on the Founding draws its arrow; Keep arrows, Whole chain, dashed planned, the edge, a click opens", async () => {
  await page.goto(`${W}/timeline`);
  const founding = page.locator('[data-testid=mark][data-label="The Founding"]').first();
  await expect(founding).toBeVisible();
  await founding.hover();
  await expect(page.getByTestId("cause-arrow")).toHaveCount(1);
  await expect(page.getByTestId("cause-arrow")).toHaveAttribute("data-to", "The Lamp Wars");
  await page.mouse.move(5, 5);
  await expect(page.getByTestId("cause-arrow")).toHaveCount(0);
  // the card's Keep arrows: they stay while panning
  await founding.hover();
  await page.getByTestId("name-card").getByRole("button", { name: "Keep arrows" }).click();
  await expect(page).toHaveURL(/keep=/);
  await expect(page.getByTestId("kept-card")).toContainText("The Founding");
  await page.getByTestId("timeline").press("ArrowRight");
  await expect(page.getByTestId("cause-arrow")).toHaveCount(1);
  // Whole chain: on to the Burning of the Quay, planned, dashed
  await page.getByTestId("kept-card").getByRole("button", { name: "Whole chain" }).click();
  await expect(page.getByTestId("cause-arrow")).toHaveCount(2);
  await expect(page.getByTestId("cause-arrow").filter({ hasNot: page.locator("[data-dashed=no]") }).last()).toHaveAttribute("data-dashed", "yes");
  // the standing filter hides the planned one
  await page.getByLabel("planned", { exact: true }).uncheck();
  await expect(page.getByTestId("cause-arrow")).toHaveCount(1);
  await page.getByLabel("planned", { exact: true }).check();
  // panned until the Founding is off screen: the arrow runs to the edge with its name
  await page.getByTestId("timeline").press("Home");
  for (let i = 0; i < 10 && (await founding.count()); i++) await page.getByTestId("timeline").press("ArrowRight");
  await expect(page.getByTestId("arrow-edge").filter({ hasText: "The Founding" })).toBeVisible({ timeout: 10_000 });
  // Esc lets them go; a click still opens the event; the told view draws none
  await page.getByTestId("timeline").press("Escape");
  await expect(page.getByTestId("kept-card")).toHaveCount(0);
  await page.getByTestId("timeline").press("Home");
  await founding.click();
  await expect(page.getByRole("heading", { name: "The Founding" })).toBeVisible();
  await page.goto(`${W}/timeline?view=told&keep=${ids["The Founding"]}`);
  await expect(page.getByTestId("cause-arrow")).toHaveCount(0);
});

test("14.7 done when: giving the Lamp Wars year −20 lists before its cause on Checks", async () => {
  await when("The Lamp Wars", -20);
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "The Founding (year 0) caused The Lamp Wars (year −20), which comes before it." })).toBeVisible();
  await page.goto(`${W}/timeline?keep=${ids["The Founding"]}`);
  await expect(page.getByTestId("before-cause")).toBeVisible();
});

test("14.8 done when: Ashgard is a place and also a character, under both, leads the Guild, nests Old Harbour; Make main", async () => {
  await page.goto(`${W}/bible/${ids.Ashgard}`);
  await page.getByTestId("also-a").selectOption("character");
  await expect(page.getByTestId("entry-kinds")).toContainText("Places · also a character");
  await page.goto(`${W}/bible/k/character`);
  const row = page.locator("tr", { hasText: "Ashgard" });
  await expect(row.getByTestId("also-tag")).toHaveText("place, also a character");
  await expect(page.getByTestId("nav-kind-character")).toContainText("2");
  await expect(page.getByTestId("nav-kind-place")).toContainText("2");
  // a character's relationship: leads the Lamp Guild
  await page.goto(`${W}/bible/${ids.Ashgard}`);
  const rel = page.getByTestId("relationships");
  await rel.getByLabel("Bible entry").fill("the Lamp Guild");
  await page.keyboard.press("Enter");
  await rel.getByLabel("How they're connected").selectOption({ label: "leads" });
  await rel.getByRole("button", { name: "Add", exact: true }).click();
  await expect(rel.locator("dl")).toContainText("the Lamp Guild");
  // still the place holding Old Harbour, on the chart
  await page.goto(`${W}/chart`);
  await expect(page.locator("[data-name='Old Harbour']").first()).toBeVisible();
  // in the prose: the place colour, "also a character"
  await api("PATCH", `${A}/chapters/${chapter[1]}`, { base_version: (await api("GET", `${A}/chapters/${chapter[1]}`)).version, body: "Ashgard woke." });
  await page.goto(`${W}/chapters/${chapter[1]}`);
  await expect(async () => {
    await page.getByTestId("editor").locator(".cm-k-place", { hasText: "Ashgard" }).dblclick();
    await expect(page.getByTestId("name-card")).toContainText("also a character", { timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  // Make main: a character now
  await page.goto(`${W}/bible/${ids.Ashgard}`);
  await page.getByTestId("make-main-character").click();
  await expect(page.getByTestId("entry-kinds")).toContainText("Characters · also a place");
  await page.goto(`${W}/chapters/${chapter[1]}`);
  await expect(page.getByTestId("editor").locator(".cm-k-character", { hasText: "Ashgard" })).toBeVisible({ timeout: 15_000 });
});
