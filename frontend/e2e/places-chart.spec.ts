// Phase 12d: the chart (docs/SPEC.md §13.7). Runs after phase 1 (name order) in its signed-in state, in a world of
// its own, "The Vale Chart", built through the API: the Iron Vale (a land) holding Old Harbour and Greywick, Old
// Harbour holding the Quay and the Lamp House, the Grey Sea around the Isle of Wrens, the Salt Marches beside the
// Iron Vale, a road and a sea route; thirteen chapters in year 312.

import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-vale-chart";
const A = "/api/worlds/the-vale-chart";
let context: BrowserContext;
let page: Page;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};
const rels: Record<string, string> = {};
const chapter: Record<number, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}
async function place(name: string, type?: string) {
  ids[name] = (await api("POST", `${A}/entities`, { name, kind: "place" })).id;
  if (type) await api("POST", `${A}/entities/${ids[name]}/facts`, { label: "type", value: type });
}
async function relate(a: string, label: string, b: string, extra: Json = {}) {
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const t = types.find((x) => x.label === label)!;
  rels[`${a}|${label}|${b}`] = (await api("POST", `${A}/relationships`, { type_id: t.id, a_id: ids[a], b_id: ids[b], ...extra })).id;
}

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const chart = () => page.getByTestId("chart");
const shape = (name: string) => chart().locator(`[data-testid="chart-place"][data-name="${name}"]`);
// a place's name is drawn above every shape and line, apart from its shape
const nameOf = (name: string) => chart().locator(`[data-testid="chart-name"][data-name="${name}"]`);
const num = async (l: Locator, a: string) => Number(await l.getAttribute(a));
async function geo(name: string) {
  const l = shape(name);
  return { x: await num(l, "data-x"), y: await num(l, "data-y"), r: await num(l, "data-r") };
}
async function within(inner: string, outer: string) {
  const i = await geo(inner);
  const o = await geo(outer);
  expect(Math.hypot(i.x - o.x, i.y - o.y) + i.r).toBeLessThanOrEqual(o.r + 1);
}

test("the world for phase 12d", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Vale Chart" });
  await api("POST", `${A}/projects`, { name: "Lamps" });
  for (let n = 1; n <= 13; n++) {
    chapter[n] = (await api("POST", `${A}/projects/lamps/chapters`, { title: `Chapter ${n}`, body: "Varren walked the quay.\n" })).id;
    await api("PATCH", `${A}/chapters/${chapter[n]}/about`, { time_at: 312 });
  }
  await place("the Iron Vale", "land");
  await place("Old Harbour", "city");
  await place("Greywick", "town");
  await place("the Quay", "district");
  await place("the Lamp House", "building");
  await place("the Grey Sea", "sea");
  await place("the Isle of Wrens", "island");
  await place("the Salt Marches", "land");
  await place("the Old Mill");
  for (const [a, b] of [["Old Harbour", "the Iron Vale"], ["Greywick", "the Iron Vale"], ["the Old Mill", "the Iron Vale"], ["the Quay", "Old Harbour"], ["the Lamp House", "Old Harbour"], ["the Isle of Wrens", "the Grey Sea"]]) await relate(a!, "inside", b!);
  await relate("the Iron Vale", "borders", "the Salt Marches");
  await relate("Old Harbour", "road to", "Greywick");
  await relate("Old Harbour", "sea route to", "the Isle of Wrens");
  await relate("Greywick", "north of", "Old Harbour");
  ids.Varren = (await api("POST", `${A}/entities`, { name: "Varren", kind: "character" })).id;
  ids["the Lamp Guild"] = (await api("POST", `${A}/entities`, { name: "the Lamp Guild", kind: "faction" })).id;
  ids["the River Wardens"] = (await api("POST", `${A}/entities`, { name: "the River Wardens", kind: "faction" })).id;
  await relate("the Lamp Guild", "controls", "the Lamp House");
  await api("PUT", `${A}/chapters/${chapter[4]}/presence/${ids.Varren}`, { place_id: ids["Old Harbour"] });
});

test("13.7.4 done when: shapes, nesting, water, borders, routes and directions", async () => {
  await page.goto(`${W}/chart`);
  await expect(shape("the Iron Vale")).toHaveAttribute("data-shape", "hexagon");
  for (const n of ["Old Harbour", "Greywick"]) await expect(shape(n)).toHaveAttribute("data-shape", "circle");
  await expect(shape("the Quay")).toHaveAttribute("data-shape", "rounded");
  await expect(shape("the Lamp House")).toHaveAttribute("data-shape", "square");
  await expect(shape("the Grey Sea")).toHaveAttribute("data-shape", "water");
  await expect(shape("the Isle of Wrens")).toHaveAttribute("data-shape", "island");
  for (const [i, o] of [["Old Harbour", "the Iron Vale"], ["Greywick", "the Iron Vale"], ["the Quay", "Old Harbour"], ["the Lamp House", "Old Harbour"], ["the Isle of Wrens", "the Grey Sea"]]) await within(i!, o!);
  // the Iron Vale shares an edge with the Salt Marches
  const v = await geo("the Iron Vale");
  const s = await geo("the Salt Marches");
  expect(Math.abs(Math.hypot(v.x - s.x, v.y - s.y) - (v.r + s.r))).toBeLessThan(12);
  // a road is a solid line, a sea route a dashed one
  await expect(chart().getByTestId("chart-road")).toHaveCount(1);
  await expect(chart().getByTestId("chart-sea")).toHaveCount(1);
  expect(await chart().getByTestId("chart-road").evaluate((e) => getComputedStyle(e).strokeDasharray)).toBe("none");
  expect(await chart().getByTestId("chart-sea").evaluate((e) => getComputedStyle(e).strokeDasharray)).not.toBe("none");
  // Greywick, north of Old Harbour, above it
  expect((await geo("Greywick")).y).toBeLessThan((await geo("Old Harbour")).y);
  // a place with no type: a lighter rounded square
  await expect(shape("the Old Mill")).toHaveAttribute("data-shape", "none");
  await expect(shape("the Old Mill")).toHaveClass(/untyped/);
  // its page opens the chart on it
  await page.goto(`${W}/bible/${ids["Old Harbour"]}`);
  await page.getByTestId("on-the-chart").click();
  await expect(page).toHaveURL(new RegExp(`/chart\\?focus=${ids["Old Harbour"]}`));
  await expect(shape("Old Harbour")).toHaveClass(/focus/);
});

test("13.7.3 done when: dragging Greywick pins it, through a reload and a new town; Reset inside the Iron Vale and Undo", async () => {
  await page.goto(`${W}/chart`);
  const g = shape("Greywick").locator(".chart-shape");
  const b = (await g.boundingBox())!;
  const rel = async () => {
    const a = await geo("Greywick");
    const o = await geo("the Iron Vale");
    return { x: a.x - o.x, y: a.y - o.y };
  };
  const before = await rel();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width / 2 + 30, b.y + b.height / 2 + 10, { steps: 8 });
  await Promise.all([page.waitForResponse((r) => r.url().includes("/chart/pins/") && r.request().method() === "PUT" && r.ok()), page.mouse.up()]);
  const pinned = await api("GET", `${A}/chart`);
  expect(pinned.pins.map((p: Json) => [p.place_id, p.container_id])).toEqual([[ids.Greywick, ids["the Iron Vale"]]]);
  await page.reload();
  await expect(shape("Greywick")).toHaveClass(/pinned/);
  const after = await rel();
  expect(Math.hypot(after.x - before.x, after.y - before.y)).toBeGreaterThan(10);
  // a new town in the Iron Vale settles around it
  await place("Newmarsh", "town");
  await relate("Newmarsh", "inside", "the Iron Vale");
  await page.reload();
  await expect(shape("Newmarsh")).toBeVisible();
  const still = await rel();
  expect(Math.hypot(still.x - after.x, still.y - after.y)).toBeLessThan(2);
  // Reset inside the Iron Vale unpins it; Undo pins it again
  await page.getByTestId("chart-reset-inside").selectOption({ label: "Reset inside the Iron Vale" });
  await expect(page.getByTestId("toast")).toContainText("Unpinned 1 place inside the Iron Vale");
  expect((await api("GET", `${A}/chart`)).pins).toEqual([]);
  await expect(shape("Greywick")).not.toHaveClass(/pinned/);
  await Promise.all([page.waitForResponse((r) => r.url().endsWith("/chart/pins") && r.request().method() === "POST" && r.ok()), page.getByTestId("toast").getByRole("button", { name: "Undo" }).click()]);
  expect((await api("GET", `${A}/chart`)).pins).toHaveLength(1);
  await expect(shape("Greywick")).toHaveClass(/pinned/);
});

test("13.7.4 done when: as of chapter 4, the Guild's shade and Varren's dot; zoomed out, Old Harbour folds; export and restore keep the pins", async () => {
  await page.goto(`${W}/chart?asof=${chapter[4]}`);
  await expect(shape("the Lamp House").getByTestId("chart-control")).toHaveAttribute("data-faction", ids["the Lamp Guild"]!);
  await expect(page.getByTestId("chart-legend")).toContainText("the Lamp Guild");
  await expect(shape("Old Harbour").locator(`[data-testid="chart-here"][data-who="Varren"]`).first()).toBeAttached();
  // zooming out folds Old Harbour to its name and count
  const c = (await chart().boundingBox())!;
  await expect(async () => {
    await page.mouse.move(c.x + c.width / 2, c.y + c.height / 2);
    await page.mouse.wheel(0, 400);
    await expect(nameOf("Old Harbour")).toHaveText("Old Harbour · 2 places", { timeout: 300 });
  }).toPass({ timeout: 15_000 });
  await expect(shape("the Quay")).toHaveCount(0);
  // export and restore keep the pins
  const zip = await (await page.request.get(`${A}/export`)).body();
  const r = await page.request.post("/api/worlds/restore", { headers: { Origin: BASE }, multipart: { file: { name: "w.zip", mimeType: "application/zip", buffer: zip } } });
  const R = `/api/worlds/${(await r.json()).slug}`;
  const ents = Object.fromEntries(((await api("GET", `${R}/entities`)) as unknown as Json[]).map((e) => [e.name, e.id]));
  const restored = await api("GET", `${R}/chart`);
  expect(restored.pins.map((p: Json) => [p.place_id, p.container_id])).toEqual([[ents.Greywick, ents["the Iron Vale"]]]);
});

test("13.7.5 done when: brushing 290–312 drives the chart, lists both changes, the scrubber steps back, clearing returns", async () => {
  // the Lamp Guild holds Greywick until year 300, the River Wardens from then; the Salt Marches border the Iron Vale
  // until chapter 12
  await relate("the Lamp Guild", "controls", "Greywick", { until_time: 300 });
  await relate("the River Wardens", "controls", "Greywick", { from_time: 300 });
  await api("DELETE", `${A}/relationships/${rels["the Iron Vale|borders|the Salt Marches"]}`);
  await relate("the Iron Vale", "borders", "the Salt Marches", { until_chapter_id: chapter[12] });
  // an event to give the Timeline a span to brush
  const e = (await api("POST", `${A}/entities`, { name: "The Charter", kind: "event" })) as Json;
  await api("PATCH", `${A}/entities/${e.id}`, { base_version: e.version, time_at: 280 });

  await page.goto(`${W}/timeline?chart=1&from=290&to=312`);
  const panel = page.getByTestId("timeline-chart");
  await expect(panel.getByTestId("chart")).toBeVisible();
  const greywick = panel.locator(`[data-testid="chart-place"][data-name="Greywick"]`);
  await expect(greywick.getByTestId("chart-control")).toHaveAttribute("data-faction", ids["the River Wardens"]!);
  await expect(greywick).toHaveClass(/outlined/);
  const changes = panel.getByTestId("chart-changes");
  await expect(changes).toContainText("Greywick · controlled by the Lamp Guild → the River Wardens · year 300");
  await expect(changes).toContainText("the Salt Marches · no longer borders the Iron Vale · chapter 12");
  // before year 300: the Guild's shade, and the two lands touching
  await panel.getByTestId("chart-scrubber").fill("0");
  await expect(panel.getByTestId("chart-scrub-at")).toHaveText("as of year 290");
  await expect(greywick.getByTestId("chart-control")).toHaveAttribute("data-faction", ids["the Lamp Guild"]!);
  const g = async (n: string) => {
    const l = panel.locator(`[data-testid="chart-place"][data-name="${n}"]`);
    return { x: await num(l, "data-x"), y: await num(l, "data-y"), r: await num(l, "data-r") };
  };
  const v = await g("the Iron Vale");
  const s = await g("the Salt Marches");
  expect(Math.abs(Math.hypot(v.x - s.x, v.y - s.y) - (v.r + s.r))).toBeLessThan(12);
  // clearing the span: the end of the story
  await page.getByTestId("clear-span").click();
  await expect(panel.getByTestId("chart-scrubber")).toHaveCount(0);
  await expect(greywick.getByTestId("chart-control")).toHaveAttribute("data-faction", ids["the River Wardens"]!);
  await expect(greywick).not.toHaveClass(/outlined/);
  // the chart page follows the Timeline too
  await page.goto(`${W}/timeline?from=290&to=312`);
  await expect(page.getByTestId("in-span")).toBeVisible();
  await page.goto(`${W}/chart?follow=1`);
  await expect(page.getByTestId("chart-follow")).toBeChecked();
  await expect(page.getByTestId("chart-changes")).toContainText("year 300");
});

test("on a phone: the chart and the Timeline with its chart fit the width", async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const url of [`${W}/chart`, `${W}/timeline?chart=1&from=290&to=312`]) {
    await page.goto(url);
    await expect(page.getByTestId("chart").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, url).toBeLessThanOrEqual(0);
  }
  await page.setViewportSize({ width: 1280, height: 720 });
});
