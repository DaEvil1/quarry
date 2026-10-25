// Phase 12c: species, roles and starting vocabulary (docs/SPEC.md §13.3–§13.5). Runs after phase 1 (name order) in
// its signed-in state, in a world of its own: "The Drowned Coast", with one book of fourteen short chapters, built
// through the API so each test starts from known data.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-drowned-coast";
const A = "/api/worlds/the-drowned-coast";
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
const entity = async (name: string, kind = "character", extra: Json = {}) => (ids[name] = (await api("POST", `${A}/entities`, { name, kind, ...extra })).id);
const fact = (name: string, label: string, value: string, extra: Json = {}) => api("POST", `${A}/entities/${ids[name]}/facts`, { label, value, ...extra });
async function relate(a: string, label: string, b: string, extra: Json = {}) {
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const t = types.find((x) => x.label === label)!;
  return api("POST", `${A}/relationships`, { type_id: t.id, a_id: ids[a], b_id: ids[b], ...extra });
}

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

// the card opened by double-clicking (a hover card may show too)
const card = () => page.getByTestId("name-card").first();
async function cardIn(n: number, name: string) {
  await page.goto(`${W}/chapters/${chapter[n]}`);
  await page.getByTestId("editor").locator(".cm-k-character", { hasText: name }).first().dblclick();
  await expect(card()).toBeVisible();
}

test("the world for phase 12c", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Drowned Coast" });
  await api("POST", `${A}/projects`, { name: "Saltwater" });
  for (const n of ["Seyla", "Varren", "Isolde", "Bram", "the Grey Tenant", "Mirelle", "Oswin", "Old Mirelle", "Tess"]) await entity(n);
  await entity("selkie", "species");
  await entity("human", "species");
  await entity("the Lamp Guild", "faction");
  for (let n = 1; n <= 14; n++) {
    const ch = await api("POST", `${A}/projects/saltwater/chapters`, { title: `Chapter ${n}`, body: "Seyla swam. Isolde waited. Varren and Bram rowed.\n" });
    chapter[n] = ch.id;
  }
  await relate("Seyla", "is a", "selkie");
  await relate("Bram", "is a", "human");
  await relate("Varren", "is a", "human");
  await relate("Seyla", "appears as", "human", { from_chapter_id: chapter[3], until_chapter_id: chapter[9] });
  await relate("the Grey Tenant", "possesses", "Isolde", { from_chapter_id: chapter[12], until_chapter_id: chapter[14] });
  await relate("Varren", "member of", "the Lamp Guild", { role: "Captain", until_chapter_id: chapter[4] });
  await relate("Isolde", "member of", "the Lamp Guild", { role: "Captain", from_chapter_id: chapter[5] });
  await relate("Oswin", "parent of", "Mirelle");
  await relate("Mirelle", "parent of", "Tess");
  await relate("Old Mirelle", "ancestor of", "Mirelle");
  await fact("selkie", "form", "aquatic");
});

test("13.3 done when: the types page lists the species types, Seyla's card reads selkie · appears as human in 5 and selkie in 10", async () => {
  await page.goto(`${W}/bible/types`);
  for (const label of ["is a", "appears as", "native to", "possesses", "ancestor of", "north of"]) await expect(page.getByTestId("relation-types").getByText(label, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Character → Species" })).toBeVisible();

  await cardIn(5, "Seyla");
  await expect(card().locator(".qcard-species")).toHaveText("selkie · appears as human");
  await cardIn(10, "Seyla");
  await expect(card().locator(".qcard-species")).toHaveText("selkie");
  // and beside the name on her page, as of a chapter
  await page.goto(`${W}/bible/${ids.Seyla}?asof=${chapter[5]}`);
  await expect(page.getByTestId("species-words")).toHaveText("selkie · appears as human");
});

test("13.3 done when: the characters table has a Species column that groups by it, and the graph colours by species", async () => {
  await page.goto(`${W}/bible/k/character`);
  const table = page.getByTestId("bible-list");
  await expect(table.locator("thead")).toContainText("Species");
  await expect(table.locator("tr", { hasText: "Seyla" })).toContainText("selkie");
  await page.getByTestId("group-by").selectOption({ label: "species" });
  await expect(page.getByTestId("section-human")).toContainText("Varren");
  await expect(page.getByTestId("section-human")).toContainText("Bram");
  await expect(page.getByTestId("section-selkie")).toContainText("Seyla");
  await expect(page.getByTestId("section-")).toContainText("Isolde");
  // clicking a value filters by it
  await table.locator("tr", { hasText: "Seyla" }).getByRole("button", { name: "selkie" }).click();
  await expect(page.getByTestId("filters")).toContainText("Species: selkie");

  await page.goto(`${W}/graph`);
  await page.getByLabel("Colour by").selectOption("species");
  await expect(page.getByTestId("species-legend")).toContainText("human (2)");
  await expect(page.getByTestId("species-legend")).toContainText("selkie (1)");
  const fill = (name: string) => page.getByTestId("graph").locator(`.gnode[data-name="${name}"] circle`).getAttribute("data-fill");
  expect(await fill("Varren")).toBe(await fill("Bram"));
  expect(await fill("Varren")).not.toBe(await fill("Seyla"));
});

test("13.4 done when: roles show on both pages, Cap offers Captain (2), and a one-at-a-time clash is listed and fixed", async () => {
  await page.goto(`${W}/bible/${ids.Varren}`);
  await expect(page.getByTestId("relationships").getByTestId("role")).toContainText("Captain");
  await page.goto(`${W}/bible/${ids["the Lamp Guild"]}`);
  const rels = page.getByTestId("relationships");
  await expect(rels.getByTestId("relationship").filter({ hasText: "Varren" })).toContainText("Captain");
  await expect(rels.getByTestId("relationship").filter({ hasText: "Isolde" })).toContainText("Captain");
  // a new member: typing Cap offers Captain (2)
  await rels.getByPlaceholder("Connect the Lamp Guild to…").fill("Bram");
  await page.keyboard.press("Enter");
  await rels.getByLabel("How they\'re connected").selectOption({ label: "has member" });
  await rels.getByLabel("New relationship standing").selectOption("canon");
  const role = rels.getByLabel("Role");
  await role.fill("Cap");
  const list = await role.getAttribute("list");
  await expect(page.locator(`datalist#${list} option`).first()).toHaveText("Captain (2)");
  await rels.getByRole("button", { name: "Cancel" }).click();

  // one at a time, from the Labels page's roles
  await page.goto(`${W}/bible/labels`);
  const roles = page.getByTestId("labels-roles");
  await roles.locator('[data-role="Captain"] summary').click();
  await roles.getByTestId("switch-one-at-a-time").check();
  await expect(roles.locator('[data-role="Captain"]')).toContainText("one at a time");
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "two Captains" })).toHaveCount(0);

  // extend Varren's until chapter 6: the clash at chapter 5
  const all = (await api("GET", `${A}/relationships`)) as unknown as Json[];
  const v = all.find((r) => r.a.name === "Varren" && r.label === "member of")!;
  await api("PATCH", `${A}/relationships/${v.id}`, { base_version: v.version, until_chapter_id: chapter[6] });
  await page.goto(`${W}/checks`);
  const clash = page.getByTestId("check").filter({ hasText: "two Captains" });
  await expect(clash).toHaveText(/the Lamp Guild has two Captains in “Chapter 5”: Varren \(from the start\) and Isolde \(from “Chapter 5”\)/);
  await clash.getByTestId("end-before").click();
  await expect(page.getByTestId("check").filter({ hasText: "two Captains" })).toHaveCount(0);
});

test("13.4: change role from here makes a new span", async () => {
  await page.goto(`${W}/bible/${ids.Isolde}`);
  const rel = page.getByTestId("relationships").getByTestId("relationship").filter({ hasText: "the Lamp Guild" });
  await rel.getByTestId("change-role").click();
  await rel.getByLabel("New role from").selectOption({ label: "Chapter 8" });
  await rel.getByLabel("New role", { exact: true }).fill("Harbourmaster");
  await rel.getByRole("button", { name: "Change" }).click();
  const rows = page.getByTestId("relationships").getByTestId("relationship").filter({ hasText: "the Lamp Guild" });
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Captain");
  await expect(rows.nth(0)).toContainText("Chapter 5 – Chapter 7");
  await expect(rows.nth(1)).toContainText("Harbourmaster");
  await expect(rows.nth(1)).toContainText("from Chapter 8");
});

test("13.5 done when: possessed by on the card, an ancestor drawn as a dashed link listed as ancestor, plane and reef offered", async () => {
  await cardIn(13, "Isolde");
  await expect(card().locator(".qcard-possessed")).toHaveText("possessed by the Grey Tenant");
  await cardIn(10, "Isolde");
  await expect(card().locator(".qcard-possessed")).toHaveCount(0);

  await page.goto(`${W}/graph?view=family&centre=${ids.Mirelle}`);
  const tree = page.getByTestId("family-tree");
  await expect(tree.getByTestId("family-lineage")).toHaveCount(1);
  await expect(tree.getByTestId("family-lineage-label")).toHaveText("generations not recorded");
  await expect(tree.locator('[data-name="Old Mirelle"]').getByTestId("family-how")).toHaveText("ancestor");
  const gen = async (name: string) => Number(await tree.locator(`[data-name="${name}"]`).getAttribute("data-gen"));
  expect((await gen("Mirelle")) - (await gen("Old Mirelle"))).toBeGreaterThanOrEqual(2);

  // a place's type offers the starting values in a world that has never used them
  await entity("the Hollow Court", "place");
  await page.goto(`${W}/bible/${ids["the Hollow Court"]}`);
  await page.getByLabel("New fact standing").selectOption("canon");
  await page.getByLabel("New fact label").fill("type");
  const value = page.getByLabel("New fact value");
  const list = await value.getAttribute("list");
  await expect(page.locator(`datalist#${list} option[value="plane"]`)).toHaveText("plane");
  await expect(page.locator(`datalist#${list} option[value="reef"]`)).toHaveCount(1);
  // a species is described with suggested facts, its values offered
  await page.goto(`${W}/bible/${ids.selkie}`);
  await expect(page.locator('#fact-labels option[value="sapient"]')).toHaveCount(1);
});
