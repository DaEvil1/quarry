// Phase 13a: the Journal as a workplace (docs/SPEC.md §14.1–§14.3). Journal entries in the editor with names, cards,
// F8, autosave, History and the offline copy; recording a fact or an event from a passage as planned, and making a
// planned fact canon in a chapter; the planning reading; sparks and questions from a passage; loose ends. Runs after
// the other specs (name order) in their signed-in state, in a world of its own built through the API.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-guild-coast";
const A = "/api/worlds/the-guild-coast";
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
const journal = async (key: string, title: string, day: string, body: string) =>
  (ids[key] = (await api("POST", `${A}/journal`, { title, entry_date: day, body })).id);

const GUILD = "The Lamp Guild has kept the Lamp lit for three hundred years.";
const TOLL = "The Lamp Guild took the first toll in lanterns.";

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

const editor = () => page.getByTestId("editor").locator(".cm-content");
const line = (text: string) => page.getByTestId("editor").locator(".cm-line", { hasText: text });
const toast = () => page.getByTestId("toast");
/** the strip a selection shows: the passage strip, or (for one short enough to be a name) the selection strip */
const selStrip = () => page.locator("[data-testid=passage-strip], [data-testid=selection-strip]");
const status = () => page.getByTestId("save-status");
/** a whole paragraph selected, as a long-press or a triple click does */
async function selectLine(text: string) {
  await line(text).click({ clickCount: 3, position: { x: 4, y: 6 } });
}

test("the world for phase 13a", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Guild Coast" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  for (const n of ["Varren", "Isolde", "Seyla"]) await entity(n);
  await entity("the Lamp Guild", "faction");
  for (let n = 1; n <= 9; n++) {
    const body = n === 9 ? "The water took Seyla at the quay.\nIsolde waited on the quay for news." : `Rain on the harbour, chapter ${n}.`;
    chapter[n] = (await api("POST", `${A}/projects/the-salt-road/chapters`, { title: n === 9 ? "The Flood" : `Chapter ${n}`, body })).id;
  }
  await journal("first", "First thoughts", "2014-05-01", "Varren keeps the lamp at the end of the world.");
  await journal("guild", "What the Guild wants", "2019-03-02", [
    GUILD,
    "Varren knows it; Isolde doesn't.",
    TOLL,
    "Ashgard waits beyond the harbour, and the guild fears Ashgard.",
    "Varren's age ?? maybe 40. What?? said Isolde.",
  ].join("\n"));
  await journal("endings", "Endings", "2020-01-10", "Seyla dies at the flood.");
  // planned in the Journal: a fact for Varren's card, and Seyla's death
  await api("POST", `${A}/entities/${ids.Varren}/facts`, { label: "title", value: "keeper", standing: "planned", planned_in_journal_id: ids.first });
  await api("POST", `${A}/entities/${ids.Seyla}/facts`, { label: "status", value: "dead", standing: "planned", planned_in_journal_id: ids.endings, planned_evidence: "Seyla dies at the flood." });
  // for the planning reading: a question of 2016 tagged with Varren, a decision of 2019 that names him
  await api("POST", `${A}/items`, { body: "How old is the keeper?", kind: "question", entities: [ids.Varren], captured_at: "2016-06-01T10:00:00+00:00" });
  await api("POST", `${A}/decisions`, { text: "Varren stays at the lamp", decided_on: "2019-06-01" });
});

test("14.1.1 done when: the entry opens in the editor with names coloured, a planned fact on the card, no Continuity", async () => {
  await page.goto(`${W}/journal`);
  const listed = page.getByTestId("journal-entry").filter({ hasText: "What the Guild wants" });
  await expect(listed.locator(".k-faction").first()).toContainText("Lamp Guild");
  await listed.getByRole("link", { name: /What the Guild wants/ }).click();
  await page.waitForURL(new RegExp(`/journal/${ids.guild}`));
  const ed = page.getByTestId("editor");
  await expect(ed.locator(".cm-k-character", { hasText: "Varren" }).first()).toBeVisible();
  await expect(ed.locator(".cm-k-character", { hasText: "Isolde" }).first()).toBeVisible();
  await expect(ed.locator(".cm-k-faction").first()).toBeVisible();
  await expect(page.getByTestId("tab-continuity")).toHaveCount(0);
  await expect(page.getByTestId("tab-looseEnds")).toBeVisible();
  // Varren's card here reads as of the end of the story, with the planned fact marked
  await expect(async () => {
    await ed.locator(".cm-k-character", { hasText: "Varren" }).first().dblclick();
    await expect(page.getByTestId("name-card")).toContainText("planned", { timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await expect(page.getByTestId("name-card")).toContainText("keeper");
  await page.keyboard.press("Escape");
});

test("14.1.1 done when: F8 steps to a possible new name and + Faction adds it to the world's bible", async () => {
  await editor().click();
  await page.keyboard.press("Control+Home");
  await expect(async () => {
    await page.keyboard.press("F8");
    await expect(page.getByTestId("selection-strip")).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await page.getByTestId("selection-strip").getByRole("button", { name: "+ Faction" }).click();
  await expect(async () => {
    const all = (await api("GET", `${A}/entities`)) as unknown as Json[];
    const made = all.find((e) => e.name === "Ashgard");
    expect(made?.kind).toBe("faction");
    expect(made?.project).toBeNull();
  }).toPass({ timeout: 10_000 });
});

test("14.1.1 done when: it autosaves, and a checkpoint in History can be restored", async () => {
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" The harbour bell rang.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await page.keyboard.press("Control+s");
  await page.getByLabel("Checkpoint label (optional)").fill("before the storm");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Checkpoint “before the storm” kept.")).toBeVisible();
  await editor().click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(" A storm came in.");
  await expect(status()).toHaveText("Saved", { timeout: 10_000 });
  await page.getByRole("button", { name: "History" }).first().click();
  const history = page.getByTestId("history");
  await history.getByRole("button", { name: /before the storm/ }).click();
  await history.getByRole("button", { name: "Restore this version" }).click();
  await expect(page.getByText("Restored. The text it replaced is in History.")).toBeVisible();
  await expect(editor()).toContainText("The harbour bell rang.");
  await expect(editor()).not.toContainText("A storm came in.");
});

test("14.1.2 done when: Record a fact from a journal passage saves it as planned, linked back to the passage", async () => {
  await page.goto(`${W}/journal/${ids.guild}`);
  await selectLine(GUILD);
  const strip = selStrip();
  await strip.getByRole("button", { name: "Record a fact" }).click();
  const form = page.getByTestId("fact-form");
  await expect(form.getByTestId("fact-entry").getByRole("button", { name: "the Lamp Guild" })).toHaveClass(/on/);
  await expect(form.getByTestId("fact-standing").getByRole("button", { name: "planned" })).toHaveAttribute("aria-pressed", "true");
  await form.getByLabel("Label").fill("age");
  await form.getByLabel("Value").fill("three hundred years");
  await form.getByLabel("Value").press("Enter");
  await expect(toast()).toContainText("Recorded “age: three hundred years” on the Lamp Guild");
  await toast().getByRole("button", { name: "Open" }).click();
  await page.waitForURL(new RegExp(`/bible/${ids["the Lamp Guild"]}`));
  const row = page.getByTestId("facts").locator("tr", { hasText: "three hundred years" });
  await expect(row.getByLabel("Standing")).toHaveValue("planned");
  const planned = row.getByTestId("planned-in");
  await expect(planned).toContainText("planned in the Journal");
  await expect(planned).toContainText("What the Guild wants");
  await planned.getByRole("link").click();
  await page.waitForURL(new RegExp(`/journal/${ids.guild}`));
  await expect(page.getByTestId("editor").locator(".cm-passage")).toContainText("three hundred years");
});

test("14.1.2 done when: a fact added on an entry page starts as planned", async () => {
  await page.goto(`${W}/bible/${ids.Isolde}`);
  await page.getByLabel("New fact label").fill("eye colour");
  await page.getByLabel("New fact value").fill("grey");
  await page.getByLabel("New fact value").press("Enter");
  await expect(page.getByTestId("facts").locator("tr", { hasText: "grey" }).getByLabel("Standing")).toHaveValue("planned");
});

test("14.1.2 done when: Record as event from the Journal makes the Founding, planned, its passage under Noted in", async () => {
  await page.goto(`${W}/journal/${ids.guild}`);
  await selectLine(GUILD);
  await selStrip().getByRole("button", { name: "Record as event" }).click();
  const form = page.getByTestId("record-form");
  await expect(form.getByTestId("record-who").getByLabel("the Lamp Guild")).toBeChecked();
  await form.getByLabel("Event").fill("The Founding");
  await form.getByLabel("Event").press("Enter");
  await expect(toast()).toContainText("Recorded “The Founding” · 1 taking part, planned");
  await toast().getByRole("button", { name: "Open" }).click();
  await expect(page.getByRole("heading", { name: "The Founding" })).toBeVisible();
  await expect(page.getByTestId("noted-in").getByTestId("note")).toContainText("three hundred years");
  await expect(page.getByTestId("noted-in")).toContainText("What the Guild wants");
  await expect(page.getByTestId("told-in")).toHaveCount(0);
  await expect(page.getByTestId("relationship").filter({ hasText: "the Lamp Guild" }).getByLabel("Standing")).toHaveValue("planned");
  // the told view lists only tellings in chapters: the Founding isn't in the book yet
  await page.goto(`${W}/timeline`);
  await page.getByTestId("tab-told").click();
  await expect(page.getByText("Not in the book yet")).toBeVisible();
  const notIn = page.locator("li", { has: page.getByRole("link", { name: "The Founding" }) });
  await expect(notIn.getByTestId("noted-count")).toContainText("noted in the Journal once");
});

test("14.1.2 done when: Record a fact in chapter 9 offers Make it canon here for Seyla's planned death", async () => {
  await page.goto(`${W}/chapters/${chapter[9]}`);
  await selectLine("The water took Seyla at the quay.");
  await selStrip().getByRole("button", { name: "Record a fact" }).click();
  const form = page.getByTestId("fact-form");
  await expect(form.getByTestId("fact-standing").getByRole("button", { name: "canon" })).toHaveAttribute("aria-pressed", "true");
  await form.getByLabel("Label").fill("status");
  await form.getByLabel("Label").press("Tab");
  const planned = form.getByTestId("planned-here");
  await expect(planned).toContainText("Planned: status dead (Journal,");
  await planned.getByRole("button", { name: "Make it canon here" }).click();
  await expect(toast()).toContainText("on Seyla");
  await page.goto(`${W}/bible/${ids.Seyla}`);
  const row = page.getByTestId("facts").locator("tr", { hasText: "dead" });
  await expect(row.getByLabel("Standing")).toHaveValue("canon");
  await expect(row).toContainText("The water took Seyla at the quay.");
  await expect(row).toContainText("The Flood");
  await expect(row.getByTestId("planned-in")).toContainText("Endings");
  const facts = (await api("GET", `${A}/entities/${ids.Seyla}`)).facts as Json[];
  expect(facts.filter((f) => f.label === "status")).toHaveLength(1);
});

test("14.2 done when: Varren's planning reading, oldest first, with years, Entries and With… Isolde", async () => {
  await page.goto(`${W}/bible/${ids.Varren}`);
  await page.getByTestId("read-planning-link").click();
  await expect(page.getByTestId("planning-count")).toContainText("Varren in the planning:");
  await expect(page.getByTestId("planning-year")).toHaveText(["2014", "2016", "2019"]);
  await expect(page.getByTestId("planning-gap").first()).toHaveText("· 2 years ·");
  const order = await page.locator("[data-testid=planning-entry], [data-testid=planning-item], [data-testid=planning-decision]").evaluateAll((xs) => xs.map((x) => x.getAttribute("data-testid")));
  expect(order).toEqual(["planning-entry", "planning-item", "planning-entry", "planning-decision"]);
  await expect(page.getByTestId("planning-item").getByTestId("tagged")).toBeVisible();
  await expect(page.getByTestId("planning-entry").first()).toContainText("Varren keeps the lamp");
  // whole entries
  await page.getByRole("tab", { name: "Entries" }).click();
  await expect(page.getByTestId("planning-entry").filter({ hasText: "What the Guild wants" })).toContainText("Lamp Guild has kept");
  // with Isolde: only what names both
  await page.getByRole("tab", { name: "Paragraphs" }).click();
  await page.getByRole("button", { name: "With…" }).click();
  await page.getByPlaceholder("Read together with…").fill("Isolde");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("planning-entry")).toHaveCount(1);
  await expect(page.getByTestId("planning-item")).toHaveCount(0);
  await expect(page.getByTestId("planning-para").first()).toContainText("Varren knows it; Isolde doesn't.");
});

test("14.3 done when: a question from a journal sentence, tagged and linked back; a parked spark", async () => {
  await page.goto(`${W}/journal/${ids.guild}`);
  await selectLine(TOLL);
  await selStrip().getByRole("button", { name: "Question" }).click();
  const form = page.getByTestId("item-form");
  await expect(form.getByLabel("the Lamp Guild")).toBeChecked();
  await form.getByLabel("Your line").fill("Who paid the first toll?");
  await form.getByLabel("Your line").press("Enter");
  await expect(toast()).toContainText("Question saved");
  await toast().getByRole("button", { name: "Open" }).click();
  await page.waitForURL(/\/items\//);
  const origin = page.getByTestId("item-origin");
  await expect(origin).toContainText("From the Journal,");
  await expect(origin).toContainText("2019");
  await expect(origin).toContainText(TOLL);
  await expect(page.getByText("the Lamp Guild").first()).toBeVisible();
  await origin.getByRole("link").click();
  await page.waitForURL(new RegExp(`/journal/${ids.guild}`));
  await expect(page.getByTestId("editor").locator(".cm-passage")).toContainText("first toll");

  await selectLine("Ashgard waits beyond the harbour");
  await selStrip().getByRole("button", { name: "Spark" }).click();
  await page.getByTestId("item-form").getByText("Park it").click();
  await page.getByTestId("item-form").getByRole("button", { name: "Save" }).click();
  await expect(toast()).toContainText("Spark saved");
  const parked = (await api("GET", `${A}/items?status=deferred`)) as unknown as Json[];
  expect(parked.some((i) => i.kind === "spark" && i.origin?.id === ids.guild)).toBe(true);
});

test("14.3 done when: the same in a chapter links the item to it, listed in the editor's Loose ends", async () => {
  await page.goto(`${W}/chapters/${chapter[9]}`);
  await selectLine("Isolde waited on the quay for news.");
  await selStrip().getByRole("button", { name: "Question" }).click();
  await page.getByTestId("item-form").getByLabel("Your line").fill("How long does she wait?");
  await page.getByTestId("item-form").getByLabel("Your line").press("Enter");
  await expect(toast()).toContainText("Question saved");
  await page.getByTestId("tab-looseEnds").click();
  const item = page.getByTestId("loose-item").filter({ hasText: "How long does she wait?" });
  await expect(item).toContainText("Isolde waited on the quay for news.");
  await item.hover();
  await expect(page.getByTestId("editor").locator(".cm-passage")).toContainText("Isolde waited");
});

test("14.3.2 done when: ?? in a journal entry is a loose end, Make a question turns it into one; What?? is not", async () => {
  await page.goto(`${W}/journal/${ids.guild}`);
  await page.getByTestId("tab-looseEnds").click();
  const tab = page.getByTestId("findings-looseEnds");
  const marker = tab.locator(".finding", { hasText: "??: " });
  await expect(marker).toHaveCount(1);
  await expect(marker).toContainText("age ?? maybe");
  await marker.getByRole("button", { name: "Make a question" }).click();
  await page.getByTestId("ask-bar").getByRole("button", { name: "Save" }).click();
  await expect(toast()).toContainText("Question saved");
  await expect(async () => {
    const items = (await api("GET", `${A}/items`)) as unknown as Json[];
    expect(items.some((i) => String(i.origin?.passage ?? "").startsWith("Varren's age ?? maybe 40. What?? said Isolde."))).toBe(true);
  }).toPass({ timeout: 10_000 });
  await page.goto(`${W}/journal`);
  await page.getByTestId("loose-tab").click();
  const loose = page.getByTestId("journal-loose");
  await expect(loose).toContainText("1 marker in 1 entry");
  await expect(loose.getByRole("link", { name: /age \?\? maybe 40/ })).toBeVisible();
});

test("14.1.1 done when: on the phone in airplane mode the entry opens and takes typing; the planning reading too", async ({ browser }) => {
  const phone = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  try {
    await p.goto(`${W}/journal/${ids.guild}`);
    await expect(p.getByTestId("editor").locator(".cm-k-faction").first()).toBeVisible();
    await p.goto(`${W}/bible/${ids.Varren}/read?in=planning`);
    await expect(p.getByTestId("planning-count")).toBeVisible();
    await p.goto("/settings");
    const offline = p.getByTestId("offline-settings");
    await offline.getByRole("button", { name: "Sync now" }).click();
    await expect(offline).toContainText("Synced.");
    await waitForServiceWorker(p);
    await phone.setOffline(true);
    await p.goto(`${W}/journal/${ids.guild}`);
    await expect(p.getByTestId("offline-copy")).toBeVisible();
    await p.getByTestId("editor").locator(".cm-content").click();
    await p.keyboard.press("Control+End");
    await p.keyboard.type(" Written on the ferry.");
    await expect(p.getByTestId("save-status")).toHaveText("Offline: kept here, retrying", { timeout: 15_000 });
    await p.goto(`${W}/bible/${ids.Varren}/read?in=planning`);
    await expect(p.getByTestId("planning-offline")).toContainText("Items and decisions need the network");
    await expect(p.getByTestId("planning-entry").first()).toContainText("Varren keeps the lamp");
    await phone.setOffline(false);
    await p.goto(`${W}/journal/${ids.guild}`);
    // what was typed offline is back in the editor, and reaches the server
    await expect(p.getByTestId("editor").locator(".cm-content")).toContainText("Written on the ferry.");
    await expect(async () => {
      const saved = await api("GET", `${A}/journal/${ids.guild}`);
      expect(saved.body).toContain("Written on the ferry.");
    }).toPass({ timeout: 20_000 });
    await expect(p.getByTestId("save-status")).toHaveText("Saved");
  } finally {
    await phone.close();
  }
});
