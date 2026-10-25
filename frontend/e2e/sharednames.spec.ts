// Phase 13c: names shared by two entries (docs/SPEC.md §14.10). Two characters called Isolde: the bare name is
// ambiguous until a choice line settles it, From here writes the line, and only settled uses count (cast, entry
// pages, Checks). Also two entries given the other name "the Warden", a choice line in the Journal, and the demo
// world's two Linnets on the phone. Runs after phase 1 (name order) in its signed-in state, in a world of its own.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-two-quays";
const A = "/api/worlds/the-two-quays";
let context: BrowserContext;
let page: Page;
let demo = "";

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};
const chapter: Record<string, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}
const entity = async (name: string, extra: Json = {}) => (ids[name] = (await api("POST", `${A}/entities`, { name, kind: "character", ...extra })).id);
const write = async (title: string, body: string) =>
  (chapter[title] = (await api("POST", `${A}/projects/the-salt-road/chapters`, { title, body })).id);
const mentionsOf = async (title: string) =>
  ((await api("GET", `${A}/chapters/${chapter[title]}`)).mentions as Json[]).map((m) => `${m.matched_text}:${m.kind}:${m.entity_name}`);

const editor = () => page.getByTestId("editor").locator(".cm-content");

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Two Quays" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  await entity("Isolde Marr", { summary: "Keeps the lamp at Old Harbour." });
  await entity("Isolde Senn", { summary: "A ferry pilot." });
  await entity("Varren Hale", { aliases: ["the Warden"] });
  await entity("Ilse Brand", { aliases: ["the Warden"] });
  await write("One", "Isolde Senn drowned off the breakwater.");
  await api("POST", `${A}/entities/${ids["Isolde Senn"]}/facts`, { label: "status", value: "dead", from_chapter_id: chapter.One });
  await write("Two", "Varren Hale waited on the quay.\n\nIsolde came down to the water.\n\nIsolde lit the lamp.");
  await write("Three", "Isolde waited for the tide.");
});

test.afterAll(async () => {
  await api("DELETE", A, { name: "The Two Quays" }).catch(() => undefined);
  if (demo) await api("DELETE", `/api/worlds/${demo}`, { name: "The Ninefold Delta (demo)" }).catch(() => undefined);
  await context.close();
});

test("14.10 done when: ambiguous Isolde, coloured as a character, its card lists both, counted for neither", async () => {
  await page.goto(`${W}/chapters/${chapter.Two}`);
  const isolde = page.getByTestId("editor").locator(".cm-name[data-hit='ambiguous']").first();
  await expect(isolde).toHaveText("Isolde");
  await expect(isolde).toHaveClass(/cm-k-character/);
  // the side panel's cast lists the claimants once
  await expect(page.getByTestId("cast-unsettled")).toContainText("Isolde? Marr · Senn");
  await expect(page.getByTestId("cast-unsettled")).toContainText("×2");
  // the card: every claimant with their one-liner, then From here
  await isolde.click();
  await page.keyboard.press("Alt+Enter");
  const card = page.getByTestId("shared-card");
  await expect(card).toContainText("Isolde Marr · Keeps the lamp at Old Harbour.");
  await expect(card).toContainText("Isolde Senn · A ferry pilot.");
  await expect(card.getByTestId("shared-strip").getByRole("button")).toHaveText(["Marr", "Senn", "Both"]);
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
  // F8 stops at it with the other marked words
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("F8");
  await expect(page.getByTestId("shared-card")).toBeVisible();
  await page.keyboard.press("Escape");

  // both entry pages show it faintly as unsettled; no first appearance from it
  for (const name of ["Isolde Marr", "Isolde Senn"]) {
    await page.goto(`${W}/bible/${ids[name]}`);
    await expect(page.getByTestId("unsettled")).toContainText("Two");
    await expect(page.getByTestId("unsettled")).toContainText("×2");
  }
  await expect(page.getByTestId("strip-line")).toContainText("+ 3 unsettled in 2 chapters");
  // Checks gives no finding though Isolde Senn is recorded dead from One
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("checks-empty")).toBeVisible();
});

test("14.10 done when: From here: Marr writes the line above the paragraph; the next chapter starts ambiguous", async () => {
  await page.goto(`${W}/chapters/${chapter.Two}`);
  await page.getByTestId("editor").locator(".cm-name[data-hit='ambiguous']").first().click();
  await page.keyboard.press("Alt+Enter");
  await page.getByTestId("shared-card").getByTestId("shared-strip").getByRole("button", { name: "Marr" }).click();
  await expect(editor()).toContainText("%% Isolde: Isolde Marr");
  // dimmed like any margin note, and both uses are now hers
  await expect(page.getByTestId("editor").locator(".cm-margin")).toHaveText("%% Isolde: Isolde Marr");
  await expect(page.getByTestId("editor").locator(".cm-name[data-hit='ambiguous']")).toHaveCount(0);
  await expect(page.getByTestId("editor").locator(`.cm-name[data-entity='${ids["Isolde Marr"]}']`)).toHaveCount(2);
  await expect.poll(() => mentionsOf("Two")).toEqual([
    "Varren Hale:exact:Varren Hale", "Isolde:alias:Isolde Marr", "Isolde:alias:Isolde Marr",
  ]);
  // the line isn't in the word count (6 + 6 + 4)
  await expect(page.getByTestId("word-count")).toContainText("16");
  // resting on a settled name: her card, then the others, Both and Unsure
  await page.getByTestId("editor").locator(`.cm-name[data-entity='${ids["Isolde Marr"]}']`).last().click();
  await page.keyboard.press("Alt+Enter");
  await expect(page.getByTestId("shared-strip").getByRole("button")).toHaveText(["Senn", "Both", "Unsure"]);
  await page.keyboard.press("Escape");
  // the next chapter starts ambiguous again
  expect(await mentionsOf("Three")).toEqual(["Isolde:ambiguous:Isolde Marr", "Isolde:ambiguous:Isolde Senn"]);
});

test("14.10 done when: Senn gives the named-after-dead finding, Both counts for each, ? unsettles", async () => {
  const two = await api("GET", `${A}/chapters/${chapter.Two}`);
  await api("PATCH", `${A}/chapters/${chapter.Two}`, { base_version: two.version, body:
    "%% Isolde: Senn\nIsolde came down to the water.\n%% Isolde: Marr, Senn\nIsolde lit the lamp.\n%% Isolde: ?\nIsolde slept." });
  expect(await mentionsOf("Two")).toEqual([
    "Isolde:alias:Isolde Senn", "Isolde:alias:Isolde Marr", "Isolde:alias:Isolde Senn",
    "Isolde:ambiguous:Isolde Marr", "Isolde:ambiguous:Isolde Senn",
  ]);
  await page.goto(`${W}/checks`);
  await expect(page.getByTestId("check").filter({ hasText: "Isolde Senn is named in “Two”" })).toContainText("after being recorded dead");
  // not in the compiled manuscript
  await page.goto(`${W}/p/the-salt-road/read`);
  await expect(page.getByText("Isolde slept.")).toBeVisible();
  await expect(page.getByText("%% Isolde")).toHaveCount(0);
  // a choice line that singles out nobody: underlined while Revising, its strip offers the claimants
  const now = await api("GET", `${A}/chapters/${chapter.Two}`);
  await api("PATCH", `${A}/chapters/${chapter.Two}`, { base_version: now.version, body: `%% Isolde: Mar\n${now.body}` });
  await page.goto(`${W}/chapters/${chapter.Two}`);
  await page.getByRole("button", { name: "Revising" }).click();
  const bad = page.getByTestId("editor").locator(".cm-bad-choice");
  await expect(bad).toHaveText("%% Isolde: Mar");
  await bad.click();
  await page.keyboard.press("Alt+Enter");
  await page.getByTestId("choice-strip").getByRole("button", { name: "Isolde Marr" }).click();
  await expect(editor()).toContainText("%% Isolde: Isolde Marr");
  await expect(bad).toHaveCount(0);
});

test("14.10 done when: two entries both called the Warden share it the same way", async () => {
  await write("Four", "The Warden spoke first.\n\n%% the Warden: Ilse Brand\nthe Warden left.");
  expect((await mentionsOf("Four")).sort()).toEqual([
    "The Warden:ambiguous:Ilse Brand", "The Warden:ambiguous:Varren Hale", "the Warden:alias:Ilse Brand",
  ]);
  await page.goto(`${W}/chapters/${chapter.Four}`);
  await expect(page.getByTestId("editor").locator(".cm-name[data-hit='ambiguous']")).toHaveText("The Warden");
  await expect(page.getByTestId("editor").locator(`.cm-name[data-entity='${ids["Ilse Brand"]}'][data-hit='alias']`)).toHaveText("the Warden");
});

test("14.10 done when: a choice line in a journal entry settles the name there", async () => {
  const j = await api("POST", `${A}/journal`, { title: "Who drowned", body: "%% Isolde: Senn\nIsolde knew the channel.\n%% not a choice, just text" });
  expect(j.mentions.map((m: Json) => `${m.kind}:${m.entity_name}`)).toEqual(["alias:Isolde Senn"]);
  await page.goto(`${W}/journal/${j.id}`);
  await expect(page.getByTestId("editor").locator(`.cm-name[data-entity='${ids["Isolde Senn"]}']`)).toHaveText("Isolde");
  // only the choice line is dimmed: another %% line is ordinary text in the Journal
  await expect(page.getByTestId("editor").locator(".cm-margin")).toHaveText("%% Isolde: Senn");
  await expect(page.getByTestId("entry-cast")).toContainText("Isolde Senn");
});

test("the demo's two Linnets on the phone: ambiguous, then settled line by line", async ({ browser }) => {
  demo = (await api("POST", "/api/worlds/demo")).slug;
  const chapters = (await api("GET", `/api/worlds/${demo}/projects/ash-season/chapters`)).chapters as Json[];
  const cartographer = chapters.find((c) => c.title === "The Cartographer")!.id;
  const phone = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const p = await phone.newPage();
  await p.goto(`/w/${demo}/chapters/${cartographer}`);
  const names = p.getByTestId("editor").locator(".cm-name");
  await expect(names.filter({ hasText: /^Linnet$/ }).first()).toBeVisible();
  const kinds = await names.filter({ hasText: /^Linnet$/ }).evaluateAll((els) => els.map((e) => e.getAttribute("data-hit")));
  expect(kinds.slice(0, 3)).toEqual(["ambiguous", "alias", "alias"]);
  // selecting the name (a long-press does that) shows the claimants and From here
  await names.filter({ hasText: /^Linnet$/ }).first().dblclick();
  await expect(p.getByTestId("shared-card")).toContainText("Linnet Sorrel");
  await expect(p.getByTestId("shared-strip").getByRole("button")).toHaveText(["Dray", "Sorrel", "Both"]);
  // after `%% Linnet: ?`, at the end of the chapter, ambiguous again
  await p.keyboard.press("Control+End");
  await expect(p.getByTestId("editor").locator(".cm-name[data-hit]").filter({ hasText: /^Linnet$/ }).last()).toHaveAttribute("data-hit", "ambiguous");
  await phone.close();
});
