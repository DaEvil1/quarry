// Phase 11: more views of the bible (docs/SPEC.md §12). The mentions strip, entries across chapters, world and project
// entries, the family tree, witnessed / gender / pronunciation, and labels and values. Runs after the other specs (name
// order) in their signed-in state, in a world of its own: "The Lamp Coast", with the books Ninefold (twenty short
// chapters) and The Salt Road, built through the API so each test starts from known data.

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
const entity = async (name: string, kind = "character", extra: Json = {}) => (ids[name] = (await api("POST", `${A}/entities`, { name, kind, ...extra })).id);
async function patchEntity(name: string, changes: Json) {
  const { entity: e } = await api("GET", `${A}/entities/${ids[name]}`);
  await api("PATCH", `${A}/entities/${ids[name]}`, { base_version: e.version, ...changes });
}
const fact = (name: string, label: string, value: string, extra: Json = {}) => api("POST", `${A}/entities/${ids[name]}/facts`, { label, value, ...extra });
async function relate(a: string, label: string, b: string, extra: Json = {}) {
  const types = (await api("GET", `${A}/relation-types`)) as unknown as Json[];
  const t = types.find((x) => x.label === label)!;
  return api("POST", `${A}/relationships`, { type_id: t.id, a_id: ids[a], b_id: ids[b], ...extra });
}
async function setBody(id: string, body: string) {
  const ch = await api("GET", `${A}/chapters/${id}`);
  await api("PATCH", `${A}/chapters/${id}`, { base_version: ch.version, body });
}

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const editor = () => page.getByTestId("editor").locator(".cm-content");
const panel = () => page.getByTestId("companion");
const strip = () => page.getByTestId("mention-strip");

test("the world for phase 11", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Lamp Coast" });
  await api("POST", `${A}/projects`, { name: "Ninefold" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  for (const n of ["Varren", "Isolde", "Oswin", "Seyla", "Bram"]) await entity(n);
  await entity("the Quay", "place");
  await entity("the Lamphouse", "place");
  await entity("the logbook", "object");
  await entity("the Lamp Guild", "faction");
  await entity("the Burning of the Quay", "event");
  // twenty short chapters: Isolde in 1–3 and 14–20 (her point of view in 2 and 15), Varren with the logbook at the
  // Lamphouse in 1, 2, 5, 9 and 14, the logbook alone in 13, the guild in 3 and 9, Oswin in 6, Seyla and Bram in 3
  const isolde = [1, 2, 3, 14, 15, 16, 17, 18, 19, 20];
  const varren = [1, 2, 5, 9, 14];
  for (let n = 1; n <= 20; n++) {
    const paras: string[] = [];
    if (isolde.includes(n)) paras.push("Isolde waited at the Quay.");
    if (varren.includes(n)) paras.push(n === 9 ? "Varren opened the logbook at the Lamphouse. The logbook was full. The logbook was old." : "Varren opened the logbook at the Lamphouse.");
    if (n === 13) paras.push("The logbook lay open.");
    if (n === 3 || n === 9) paras.push("The Lamp Guild met.");
    if (n === 3) paras.push("Seyla smiled. Bram rang the bell.");
    if (n === 6) paras.push("Oswin rowed out.");
    if (!paras.length) paras.push("Rain on the water.");
    const ch = await api("POST", `${A}/projects/ninefold/chapters`, {
      title: `Chapter ${n}`,
      body: paras.join("\n\n") + "\n",
      ...(n === 2 || n === 15 ? { pov_entity_id: ids.Isolde } : {}),
    });
    chapter[n] = ch.id;
  }
  await relate("Varren", "parent of", "Isolde");
  await relate("Varren", "parent of", "Oswin");
  await relate("Varren", "married to", "Seyla", { from_chapter_id: chapter[3] });
  await patchEntity("Isolde", { gender: "female" });
  await patchEntity("Oswin", { gender: "male" });
  await patchEntity("Seyla", { gender: "female" });
  // events and places with a type
  for (const [name, type] of [["Lantern Night", "Festival"], ["Spring Fair", "Festival"], ["Ash Fair", "Festival"], ["Harvest Fair", "Festival"],
    ["The Siege", "Battle"], ["The Rout", "Battle"], ["The Wedding", "Wedding"], ["Toll Day", "Feast"]] as const) {
    await entity(name, "event");
    await fact(name, "type", type);
  }
  for (const [name, type] of [["Saltmouth", "City"], ["Greyport", "City"], ["Lowtown", "City"], ["Feast Hall", "Feast"]] as const) {
    await entity(name, "place");
    await fact(name, "type", type);
  }
});

test("12.1 done when: Isolde's strip is filled at 1–3 and 14–20, a 10-chapter gap is labelled, her POV marked, and as of 10 dims 11–20", async () => {
  await page.goto(`${W}/bible/${ids.Isolde}`);
  await expect(strip()).toBeVisible();
  const filled = await strip().locator(".strip-cell").evaluateAll((cells) => cells.filter((c) => c.getAttribute("data-count") !== "0").map((c) => Number(c.getAttribute("data-n"))));
  expect(filled).toEqual([1, 2, 3, 14, 15, 16, 17, 18, 19, 20]);
  await expect(strip().locator('.strip-cell[data-n="4"]').getByTestId("strip-gap")).toHaveText("10 chapters");
  await expect(strip().getByTestId("strip-gap")).toHaveCount(1);
  await expect(page.getByTestId("strip-line")).toHaveText("In 10 of 20 chapters · first in 1 · last in 20 · longest gap: 10 chapters (4–13)");
  const pov = await strip().locator(".strip-cell:has(.pov.on)").evaluateAll((cells) => cells.map((c) => Number(c.getAttribute("data-n"))));
  expect(pov).toEqual([2, 15]);
  // resting on a cell says which chapter and how often; clicking opens it
  await strip().locator('.strip-cell[data-n="2"]').hover();
  await expect(strip().locator(".strip-tip")).toHaveText("2. Chapter 2 · named once · point of view");

  await page.getByTestId("as-of").selectOption({ label: "Chapter 10" });
  const later = await strip().locator(".strip-cell.later").evaluateAll((cells) => cells.map((c) => Number(c.getAttribute("data-n"))));
  expect(later).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
  await expect(strip().locator(".strip-cell.asof")).toHaveAttribute("data-n", "10");

  await strip().locator('.strip-cell[data-n="3"]').click();
  await expect(page.getByLabel("Chapter title")).toHaveValue("Chapter 3");
});

test("12.3 done when: four chosen rows across the book, ticking two with all of them, and the Characters chip gives today's grid", async () => {
  await page.goto(`${W}/where?kinds=`);
  const add = page.getByTestId("where-add").getByPlaceholder("Add…");
  for (const name of ["Varren", "Isolde", "the logbook", "the Lamp Guild"]) {
    await add.fill(name);
    await page.keyboard.press("Enter");
    await expect(page.getByTestId(`where-${name}`)).toBeVisible();
  }
  const grid = page.getByTestId("where-grid");
  await expect(grid.locator("tbody tr")).toHaveCount(4);
  await expect(grid.locator("thead .chapter-head")).toHaveCount(20);
  // places for the two characters (named in the same paragraph), shaded counts for the logbook and the guild
  await expect(page.getByTestId("where-Varren").locator("td[data-chapter='Chapter 1']")).toContainText("the Lamphouse?");
  await expect(page.getByTestId("where-Isolde").locator("td[data-chapter='Chapter 1']")).toContainText("the Quay?");
  await expect(page.getByTestId("where-the logbook").locator("td[data-chapter='Chapter 9']")).toHaveAttribute("data-count", "3");
  await expect(page.getByTestId("where-the logbook").locator("td[data-chapter='Chapter 9']")).toHaveClass(/s3/);
  await expect(page.getByTestId("where-the logbook").locator("td[data-chapter='Chapter 1']")).toHaveClass(/s1/);
  await expect(page.getByTestId("where-the Lamp Guild").locator("td[data-chapter='Chapter 3']")).toHaveAttribute("data-count", "1");
  // the point of view under the chapter's head
  await expect(grid.locator(".chapter-head[data-n='2'] .pov-head")).toHaveText("Isolde");

  // do these share a chapter?
  await page.getByTestId("where-Varren").getByTestId("where-tick").check();
  await page.getByTestId("where-the logbook").getByTestId("where-tick").check();
  await page.getByTestId("where-share").selectOption("every");
  await expect(grid.locator("thead .chapter-head")).toHaveCount(5);
  await expect(page.getByTestId("share-line")).toHaveText("Varren and the logbook are named together in 5 of 20 chapters");
  // the choice is in the address
  await expect(page).toHaveURL(/share=every/);

  // a row's × hides it, listed under the grid to show again
  await page.getByTestId("where-the Lamp Guild").getByRole("button", { name: "Hide the Lamp Guild" }).click();
  await expect(page.getByTestId("hidden-rows")).toContainText("the Lamp Guild");

  // Characters alone: today's grid, where clicking a cell still records "is at"
  await page.goto(`${W}/where?kinds=character`);
  await expect(page.getByTestId("where-Oswin")).toBeVisible();
  await expect(page.getByTestId("where-the logbook")).toHaveCount(0);
  const cell = page.getByTestId("where-Isolde").locator("td[data-chapter='Chapter 14']");
  await cell.getByRole("button").click();
  await cell.getByLabel("Is at").selectOption({ label: "the Quay" });
  await expect(cell).toHaveClass(/recorded/);
  await expect(cell).toContainText("the Quay");
  await expect(cell).not.toContainText("?");
});

test("12.4 done when: Mirelle made from a Salt Road chapter starts in its bible, is Elsewhere in Ninefold, and is shared in one click", async () => {
  const salt = await api("POST", `${A}/projects/the-salt-road/chapters`, { title: "Salt one", body: "Mirelle walked the salt road.\n" });
  chapter[101] = salt.id;
  await page.goto(`${W}/chapters/${salt.id}`);
  await editor().getByText("Mirelle walked").waitFor();
  await page.getByTestId("editor").locator(".cm-line").first().click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("Home");
  await page.keyboard.press("Control+Shift+ArrowRight");
  const sel = page.getByTestId("selection-strip");
  await expect(sel).toBeVisible();
  await sel.getByRole("button", { name: "+ Character" }).click();
  await expect(page.getByTestId("editor").locator(".cm-name.cm-k-character", { hasText: "Mirelle" })).toBeVisible();

  const mirelle = ((await api("GET", `${A}/entities`)) as unknown as Json[]).find((e) => e.name === "Mirelle")!;
  ids.Mirelle = mirelle.id;
  expect(mirelle.project).toBe("the-salt-road");
  await page.goto(`${W}/bible/${ids.Mirelle}`);
  await expect(page.getByTestId("level")).toHaveValue("the-salt-road");

  // listed under In this book with The Salt Road chosen, under Elsewhere with Ninefold
  await page.goto(`${W}/bible/k/character?book=the-salt-road`);
  await expect(page.getByTestId("section-in")).toContainText("Mirelle");
  await page.goto(`${W}/bible/k/character?book=ninefold`);
  const elsewhere = page.getByTestId("section-else");
  await expect(elsewhere).toContainText("Mirelle");
  await expect(elsewhere.locator("tr", { hasText: "Mirelle" }).getByTestId("where-used")).toHaveText("only in The Salt Road");
  await expect(page.getByTestId("section-in")).toContainText("Isolde");
  await expect(page.getByRole("button", { name: "Level" })).toBeVisible();

  // named in a Ninefold chapter: the Archivist offers to share her with the world
  await setBody(chapter[7]!, "Mirelle came down to the quay.\n");
  await page.goto(`${W}/chapters/${chapter[7]}`);
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await panel().getByTestId("tab-archivist").click();
  const finding = panel().getByTestId("findings-archivist").locator(".finding", { hasText: "Mirelle is in The Salt Road's bible and is named here." });
  await expect(finding).toBeVisible();
  await finding.getByRole("button", { name: "Share with the world" }).click();
  await expect(panel().getByTestId("findings-archivist")).not.toContainText("Mirelle is in The Salt Road's bible");
  await page.goto(`${W}/bible/${ids.Mirelle}`);
  await expect(page.getByTestId("level")).toHaveValue("");

  // a world with one project shows no levels
  await api("POST", "/api/worlds", { name: "Lone Shore" });
  await api("POST", "/api/worlds/lone-shore/projects", { name: "Only Book" });
  const lone = await api("POST", "/api/worlds/lone-shore/entities", { name: "Hale", kind: "character", project: "only-book" });
  expect(lone.project).toBeNull();
  await page.goto(`/w/lone-shore/bible/${lone.id}`);
  await expect(page.getByRole("heading", { name: "Hale" })).toBeVisible();
  await expect(page.getByTestId("level")).toHaveCount(0);
  await page.goto("/w/lone-shore/bible/k/character");
  await expect(page.getByTestId("bible-list")).toContainText("Hale");
  await expect(page.getByRole("button", { name: "Level" })).toHaveCount(0);
  await expect(page.getByTestId("bible-book")).toHaveCount(0);
});

test("12.2 done when: three generations around Mirelle, kin words by gender, worked out on Isolde's page, and as of chapter 2 no Seyla", async () => {
  await relate("Oswin", "parent of", "Mirelle");
  await patchEntity("Mirelle", { gender: "female" });
  const before = ((await api("GET", `${A}/relationships`)) as unknown as Json[]).length;
  // Varren's gender set on his page
  await page.goto(`${W}/bible/${ids.Varren}`);
  await page.getByTestId("gender").selectOption("male");
  await expect(page.getByTestId("gender")).toHaveValue("male");

  await page.goto(`${W}/graph?view=family&centre=${ids.Mirelle}`);
  const tree = page.getByTestId("family-tree");
  await expect(tree.getByTestId("family-person")).toHaveCount(5);
  const gens = await tree.getByTestId("family-person").evaluateAll((ps) => Object.fromEntries(ps.map((p) => [p.getAttribute("data-name"), p.getAttribute("data-gen")])));
  expect(gens).toEqual({ Varren: "0", Seyla: "0", Isolde: "1", Oswin: "1", Mirelle: "2" });
  await expect(tree.locator('[data-name="Varren"]').getByTestId("family-how")).toHaveText("grandfather");
  await expect(tree.locator('[data-name="Isolde"]').getByTestId("family-how")).toHaveText("aunt");
  await expect(tree.locator(".fline.married")).toHaveCount(2);

  // Isolde's page: dimmed and with their paths
  await page.goto(`${W}/bible/${ids.Isolde}`);
  const kin = page.getByTestId("family-worked-out");
  await expect(kin).toContainText(/brother · Oswin\s*\(via Varren\)/);
  await expect(kin).toContainText(/niece · Mirelle\s*\(via Varren → Oswin\)/);
  await expect(kin).toContainText(/stepmother · Seyla\s*\(via Varren\)/);
  await expect(page.getByTestId("family-tree-link")).toBeVisible();
  // as of chapter 2 Varren hasn't married Seyla yet
  await page.getByTestId("as-of").selectOption({ label: "Chapter 2" });
  await expect(kin).not.toContainText("Seyla");
  await expect(kin).toContainText("niece · Mirelle");
  await page.getByTestId("family-tree-link").click();
  await expect(page.getByTestId("family-tree").getByTestId("family-person")).toHaveCount(4);
  await expect(page.getByTestId("family-tree").locator('[data-name="Seyla"]')).toHaveCount(0);

  // not set gives the general word; nothing was added to the recorded relationships
  await page.goto(`${W}/bible/${ids.Oswin}`);
  await page.getByTestId("gender").selectOption("");
  await page.goto(`${W}/bible/${ids.Isolde}`);
  await expect(page.getByTestId("family-worked-out")).toContainText(/sibling · Oswin\s*\(via Varren\)/);
  await page.goto(`${W}/bible/${ids.Mirelle}`);
  await expect(page.getByTestId("family-worked-out")).toContainText("aunt · Isolde");
  expect(((await api("GET", `${A}/relationships`)) as unknown as Json[]).length).toBe(before);
});

test("12.5 done when: witnessed reads back on the event, pronunciation shows beside the name, and gender on the card only when set", async () => {
  await page.goto(`${W}/bible/types`);
  const group = page.locator("section", { has: page.getByRole("heading", { name: "Character → Event" }) });
  await expect(group).toContainText("witnessed");
  await relate("Varren", "witnessed", "the Burning of the Quay");
  await page.goto(`${W}/bible/${ids["the Burning of the Quay"]}`);
  const rel = page.getByTestId("relationships");
  await expect(rel.locator("dt")).toContainText(["witnessed by"]);
  await expect(rel.locator("dd")).toContainText(["Varren"]);

  // the fact picker offers pronunciation, which then shows after the name
  await page.goto(`${W}/bible/${ids.Varren}`);
  await expect(page.locator('#fact-labels option[value="pronunciation"]')).toHaveCount(1);
  await expect(page.locator('#fact-labels option[value="gender"]')).toHaveCount(0);
  await page.getByLabel("New fact label").fill("pronunciation");
  await page.getByLabel("New fact value").fill("VAR-en");
  await page.getByTestId("facts").getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByTestId("pronunciation")).toHaveText("VAR-en");
  // an existing character not set
  await page.goto(`${W}/bible/${ids.Bram}`);
  await expect(page.getByTestId("gender")).toHaveValue("");

  // on the card: the pronunciation and "male" after the name, not repeated among the facts; nothing for one not set
  await page.goto(`${W}/chapters/${chapter[1]}`);
  await page.getByTestId("editor").locator(".cm-k-character", { hasText: "Varren" }).dblclick();
  const card = page.getByTestId("name-card");
  await expect(card.locator(".qcard-said")).toHaveText("VAR-en");
  await expect(card.locator(".qcard-gender")).toHaveText("male");
  await expect(card.locator(".qcard-facts")).toHaveCount(0);
  await page.goto(`${W}/chapters/${chapter[6]}`);
  await page.getByTestId("editor").locator(".cm-k-character", { hasText: "Oswin" }).dblclick();
  await expect(page.getByTestId("name-card")).toContainText("Oswin");
  await expect(page.getByTestId("name-card").locator(".qcard-gender")).toHaveCount(0);
});

test("12.6.1 done when: typing fest as an event's type offers Festival (4) and nothing from the places, and saves that spelling", async () => {
  await entity("Harbour Fete", "event");
  await page.goto(`${W}/bible/${ids["Harbour Fete"]}`);
  await page.getByLabel("New fact label").fill("type");
  const value = page.getByLabel("New fact value");
  await value.fill("fest");
  const list = await value.getAttribute("list");
  const options = page.locator(`datalist#${list} option`);
  await expect(options.first()).toHaveAttribute("value", "Festival");
  await expect(options.first()).toHaveText("Festival (4)");
  await expect(page.locator(`datalist#${list} option[value="City"]`)).toHaveCount(0);
  await value.fill("Festival");
  await page.getByTestId("facts").getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByTestId("facts").locator("tr", { hasText: "type" })).toContainText("Festival");
  const facts = (await api("GET", `${A}/entities/${ids["Harbour Fete"]}`)).facts as Json[];
  expect(facts.map((f) => [f.label, f.value])).toEqual([["type", "Festival"]]);
});

test("12.6.2 done when: clicking Festival filters the Events table, kept in the address, and Group by type splits it with counts", async () => {
  await page.goto(`${W}/bible/k/event`);
  const table = page.getByTestId("bible-list");
  await table.locator(".value-link", { hasText: "Festival" }).first().click();
  await expect(page).toHaveURL(/f=type(%3A|:)Festival/);
  await expect(page.getByTestId("filters")).toContainText("type: Festival");
  await expect(table.locator("tbody tr:not(.section-head)")).toHaveCount(5);
  await expect(table).not.toContainText("The Siege");
  await page.reload();
  await expect(table.locator("tbody tr:not(.section-head)")).toHaveCount(5);
  await page.getByTestId("filters").getByRole("button", { name: "Remove the filter type: Festival" }).click();

  await page.getByTestId("group-by").selectOption("type");
  const heads = await table.locator("tr.section-head").allTextContents();
  expect(heads.map((h) => h.replace(/\s+/g, " ").trim())).toEqual(["Festival (5)", "Battle (2)", "Feast (1)", "Wedding (1)", "no type (1)"]);
  // a group's heading filters to it
  await table.locator("tr.section-head").first().getByRole("button", { name: "Festival" }).click();
  await expect(page.getByTestId("filters")).toContainText("type: Festival");
});

test("12.6.3 done when: the Labels page has type for events and for places, merging Feast into Festival changes only the events, and Undo", async () => {
  await page.goto(`${W}/bible`);
  await page.getByTestId("labels-link").click();
  const events = page.getByTestId("labels-event").locator('details[data-label="type"]');
  const places = page.getByTestId("labels-place").locator('details[data-label="type"]');
  await expect(events.locator("summary")).toContainText("Festival 5 · Battle 2");
  await expect(places.locator("summary")).toContainText("City 3");
  await expect(events.locator("summary")).toContainText("of 10 events");

  await events.locator("summary").click();
  const feast = events.locator('li[data-value="Feast"]');
  await feast.getByLabel("Rename or merge Feast").fill("Festival");
  await feast.getByRole("button", { name: "Rename" }).click();
  const toast = page.getByTestId("toast");
  await expect(toast).toContainText("Changed 1 fact on 1 event.");
  await expect(events.locator("summary")).toContainText("Festival 6");
  await expect(events.locator('li[data-value="Feast"]')).toHaveCount(0);
  await expect(places.locator("summary")).toContainText("Feast 1");
  await toast.getByRole("button", { name: "Undo" }).click();
  await expect(events.locator('li[data-value="Feast"]')).toHaveCount(1);
  await expect(events.locator("summary")).toContainText("Festival 5");
});

test("12.6.5 done when: common labels are offered, the third use asks once without taking focus, and expected labels are the Archivist's", async () => {
  // starting suggestions in every world
  await page.goto(`${W}/bible/${ids["the Burning of the Quay"]}`);
  await expect(page.locator('#fact-labels option[value="type"]')).toHaveCount(1);
  await page.goto(`${W}/bible/${ids.Seyla}`);
  await expect(page.locator('#fact-labels option[value="pronouns"]')).toHaveCount(1);

  await fact("Isolde", "eye colour", "grey");
  await fact("Oswin", "eye colour", "brown");
  // the third character: asked once, inline, and the label field keeps the focus
  await page.goto(`${W}/bible/${ids.Mirelle}`);
  await page.getByLabel("New fact label").fill("eye colour");
  await page.getByLabel("New fact value").fill("green");
  await page.getByLabel("New fact value").press("Enter");
  const prompt = page.getByTestId("label-prompt");
  await expect(prompt).toHaveText(`3 characters have "eye colour" now · Expect it on every character? · Not now`);
  await expect(page.getByLabel("New fact label")).toBeFocused();
  await page.keyboard.type("hair");
  await expect(page.getByLabel("New fact label")).toHaveValue("hair");
  await prompt.getByRole("button", { name: "Not now" }).click();
  await expect(prompt).toHaveCount(0);
  // common now: first among the labels, and offered as "Add:" on a character without it; no finding anywhere
  await page.goto(`${W}/bible/${ids.Seyla}`);
  await expect(page.locator("#fact-labels option").first()).toHaveAttribute("value", "eye colour");
  await expect(page.getByTestId("add-line")).toContainText("eye colour");
  await expect(page.getByTestId("entity-findings")).toHaveCount(0);
  // a fourth doesn't ask again
  await page.goto(`${W}/bible/${ids.Varren}`);
  await page.getByLabel("New fact label").fill("eye colour");
  await page.getByLabel("New fact value").fill("green");
  await page.getByLabel("New fact value").press("Enter");
  await expect(page.getByTestId("facts")).toContainText("green");
  await expect(page.getByTestId("label-prompt")).toHaveCount(0);

  // "Expect it" from the inline line, for another label
  await fact("Isolde", "hair", "black");
  await fact("Oswin", "hair", "red");
  await page.goto(`${W}/bible/${ids.Mirelle}`);
  await page.getByLabel("New fact label").fill("hair");
  await page.getByLabel("New fact value").fill("fair");
  await page.getByLabel("New fact value").press("Enter");
  await page.getByTestId("label-prompt").getByRole("button", { name: "Expect it on every character?" }).click();
  await expect(page.getByTestId("label-prompt")).toContainText(`“hair” is expected on every character now`);

  // "eye colour" expected from the Labels page
  await page.goto(`${W}/bible/labels`);
  const eyes = page.getByTestId("labels-character").locator('details[data-label="eye colour"]');
  await eyes.locator("summary").click();
  await eyes.getByTestId("switch-expected").check();
  await expect(eyes.locator("summary")).toContainText("expected");
  await expect(eyes.getByTestId("without")).toContainText("Seyla");

  // the Archivist, while Revising, lists the named characters without it
  await page.goto(`${W}/chapters/${chapter[3]}`);
  await page.getByTestId("mode").getByRole("button", { name: "Revising" }).click();
  await panel().getByTestId("tab-archivist").click();
  const found = panel().getByTestId("findings-archivist");
  await expect(found).toContainText("Seyla has no eye colour (expected for characters).");
  await expect(found).toContainText("Bram has no eye colour (expected for characters).");
  await expect(found).not.toContainText("Isolde has no eye colour");
  await found.locator(".finding", { hasText: "Seyla has no eye colour" }).getByRole("button", { name: "Not for this one" }).click();
  await expect(found).not.toContainText("Seyla has no eye colour");
  await expect(found).toContainText("Bram has no eye colour");
  await expect(found).toContainText("Seyla has no hair");
  // Add it opens the fact on the entry
  await found.locator(".finding", { hasText: "Bram has no eye colour" }).getByRole("button", { name: "Add it" }).click();
  await expect(page.getByRole("heading", { name: "Bram" })).toBeVisible();
  await expect(page.getByLabel("New fact label")).toHaveValue("eye colour");
  await expect(page.getByLabel("New fact value")).toBeFocused();
  await expect(page.getByTestId("entity-findings")).toContainText("Bram has no eye colour (expected for characters).");
});

test("12.6.4 done when: with several values on, Varren's green and red show as two chips on his page and card and Checks has no conflict", async () => {
  const { facts } = await api("GET", `${A}/entities/${ids.Varren}`);
  const green = (facts as Json[]).find((f) => f.label === "eye colour")!;
  await api("PATCH", `${A}/facts/${green.id}`, { base_version: green.version, from_chapter_id: chapter[1] });
  await fact("Varren", "eye colour", "red", { from_chapter_id: chapter[1] });

  await page.goto(`${W}/checks`);
  const conflict = page.getByTestId("check").filter({ hasText: "Varren: “eye colour” is both" });
  await expect(conflict).toBeVisible();

  await page.goto(`${W}/bible/labels`);
  const eyes = page.getByTestId("labels-character").locator('details[data-label="eye colour"]');
  await eyes.locator("summary").click();
  await eyes.getByTestId("switch-several").check();
  await expect(eyes.locator("summary")).toContainText("several values");

  await page.goto(`${W}/bible/${ids.Varren}`);
  await expect(page.getByTestId("value-chip")).toHaveCount(2);
  await expect(page.getByTestId("value-chips")).toContainText("green");
  await expect(page.getByTestId("value-chips")).toContainText("red");
  await page.goto(`${W}/chapters/${chapter[1]}`);
  // (the cards on the device catch up with the switch a moment after the page opens)
  await expect(async () => {
    await page.getByTestId("editor").locator(".cm-k-character", { hasText: "Varren" }).dblclick();
    await expect(page.getByTestId("name-card").locator(".qcard-chip")).toHaveText(["green", "red"], { timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "Varren: “eye colour”" })).toHaveCount(0);

  // switched off, the conflict is back; "Both are true" on the finding switches it on again
  await page.goto(`${W}/bible/labels`);
  await eyes.locator("summary").click();
  await eyes.getByTestId("switch-several").uncheck();
  await expect(eyes.locator("summary")).not.toContainText("several values");
  await page.goto(`${W}/checks`);
  await expect(conflict).toBeVisible();
  await conflict.getByRole("button", { name: "Both are true (several values)" }).click();
  await expect(page.getByTestId("check").filter({ hasText: "Varren: “eye colour”" })).toHaveCount(0);
});
