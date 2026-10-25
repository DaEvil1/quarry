// Phase 14: decisions with follow-ups (docs/SPEC.md §16). The follow-up step after a close in Triage (keys f, w, t, x,
// Enter, Esc; any Triage key skips it), its forms and the chapter a decision names; the pill and the follow-up list
// on the Decisions page, the entry page and the front page; Drop, Detach and deleting a row; the gap line in a written
// chapter's Loose ends with Not yet and Make it canon here; the Decisions filter and To follow through; the decided
// date on a Checks finding; and the step on the phone. Runs after phase 1 in its signed-in state, in a world of its own.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-salt-delta";
const A = "/api/worlds/the-salt-delta";
const DEATH = "Varren dies at the end of chapter 9";
let context: BrowserContext;
let page: Page;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};
const chapters: string[] = [];

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}
const question = (body: string) =>
  api("POST", `${A}/items`, { body, kind: "question", project: "the-salt-road", entities: [ids.Varren, ids.Isolde] });
const decisionByText = async (text: string) => ((await api("GET", `${A}/decisions`)) as unknown as Json[]).find((d) => d.text === text)!;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Salt Delta" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  for (const name of ["Varren", "Isolde"]) ids[name] = (await api("POST", `${A}/entities`, { name, kind: "character" })).id;
  for (let i = 1; i <= 10; i++) {
    const body = i === 10 ? "Varren walked along the quay at dawn.\n" : i < 9 ? `Part ${i} is written.\n` : "";
    chapters.push((await api("POST", `${A}/projects/the-salt-road/chapters`, { title: i === 9 ? "The Drowned Bell" : `Part ${i}`, body })).id);
  }
  // oldest first in Triage
  for (const q of ["Is the bell cracked?", "Who rings it?", "When does Varren die?", "Harvest me", "Accept me"]) await question(q);
});

test.afterAll(async () => {
  await api("DELETE", A, { name: "The Salt Delta" }).catch(() => undefined);
  await context.close();
});

test("16.3 done when: the step in Triage, skipped by Enter and by a Triage key; f, t, Esc; nothing for no decision", async () => {
  await page.goto(`${W}/triage`);
  const card = page.getByTestId("triage-item");
  const step = page.getByTestId("triage-step");
  // Enter skips it
  await expect(card).toContainText("Is the bell cracked?");
  await page.keyboard.press("a");
  await page.keyboard.type("The bell is cracked from the start");
  await page.keyboard.press("Enter");
  await expect(step).toContainText("Decision logged");
  await expect(step).toContainText("f fact");
  await expect(card).toContainText("Who rings it?");
  await page.keyboard.press("Enter");
  await expect(step).toHaveCount(0);
  // a, a Triage key, skips it and accepts the next item
  await page.keyboard.press("a");
  await page.keyboard.type("Isolde rings it");
  await page.keyboard.press("Enter");
  await expect(step).toBeVisible();
  await expect(card).toContainText("When does Varren die?");
  await page.keyboard.press("a");
  await expect(step).toHaveCount(0);
  await expect(page.locator("#triage-prompt")).toBeFocused();
  // f: the fact form, with the chapter the decision names offered, used only after a click
  await page.keyboard.type(DEATH);
  await page.keyboard.press("Enter");
  await expect(step).toBeVisible();
  await page.keyboard.press("f");
  const form = page.getByTestId("fu-fact-form");
  await expect(form.getByRole("button", { name: "Varren" })).toHaveAttribute("aria-pressed", "true");
  await expect(form.getByTestId("fu-offer")).toContainText("Named in the decision: chapter 9, The Drowned Bell");
  await form.getByLabel("Follow-up fact label").fill("status");
  await form.getByLabel("Follow-up fact value").fill("dead");
  await form.getByTestId("fu-offer").getByRole("button", { name: "From" }).click();
  await expect(form.locator(".span-text")).toContainText("The Drowned Bell");
  await form.getByLabel("Follow-up fact value").press("Enter");
  await expect(page.getByTestId("toast").last()).toContainText('Planned "status: dead" on Varren · follows the decision');
  await expect(step.getByTestId("followup-row")).toContainText("+ another");
  // Esc in a form goes back to the row without saving
  await page.keyboard.press("t");
  await expect(page.getByTestId("fu-task-form")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(step.getByTestId("followup-row")).toBeVisible();
  // t: a task, Varren and Isolde ticked, chapter 9 offered unticked; once ticked, it is in chapter 9's Loose ends
  await page.keyboard.press("t");
  const task = page.getByTestId("fu-task-form");
  await expect(task.getByRole("button", { name: "✓ Varren" })).toHaveAttribute("aria-pressed", "true");
  await expect(task.getByRole("button", { name: "✓ Isolde" })).toHaveAttribute("aria-pressed", "true");
  await expect(task.getByTestId("fu-task-chapter")).toHaveAttribute("aria-pressed", "false");
  await task.getByLabel("Follow-up task").fill("Plant the bell's crack in chapter 4");
  await task.getByTestId("fu-task-chapter").click();
  await task.getByLabel("Follow-up task").press("Enter");
  await expect(step.getByTestId("followup-row")).toContainText("+ another");
  await page.keyboard.press("Enter");
  await expect(step).toHaveCount(0);
  // a harvest note, and an empty decision line, offer nothing
  await expect(card).toContainText("Harvest me");
  await page.keyboard.press("h");
  await page.keyboard.type("Keep the bell");
  await page.keyboard.press("Enter");
  await expect(card).toContainText("Accept me");
  await expect(step).toHaveCount(0);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Inbox clear")).toBeVisible();
  await expect(step).toHaveCount(0);

  const d = await decisionByText(DEATH);
  expect(d.followups).toEqual({ todo: 2, done: 0, dropped: 0 });
  const items = (await api("GET", `${A}/chapters/${chapters[8]}/items`)) as unknown as Json[];
  expect(items.map((i) => i.body)).toEqual(["Plant the bell's crack in chapter 4"]);
});

test("16.1 and 16.2 done when: the pill and the list, made canon, Drop, Detach, + follow-up and attach, a delete that warns", async () => {
  const d = await decisionByText(DEATH);
  // on Varren's page: the fact says what it follows, the decision has its pill
  await page.goto(`${W}/bible/${ids.Varren}`);
  const facts = page.getByTestId("facts");
  await expect(facts.getByTestId("follows-line")).toContainText("follows the decision of");
  const line = page.getByTestId("entity-decisions").locator("li").filter({ hasText: DEATH });
  await expect(line.getByTestId("fu-pill")).toHaveText("2 of 2 to do");
  // the standing pill to canon makes the fact done
  await facts.getByLabel("Standing").first().selectOption("canon");
  await expect(line.getByTestId("fu-pill")).toHaveText("1 of 2 to do");
  // on the Decisions page: the list, to do first; Drop the task, then Undo
  await page.goto(`${W}/decisions`);
  const row = page.locator(`#d-${d.id}`);
  await row.getByTestId("fu-pill").click();
  const lines = row.getByTestId("fu-line");
  await expect(lines.first()).toContainText("to do");
  await expect(lines.first()).toContainText("Plant the bell's crack in chapter 4");
  await expect(lines.nth(1)).toContainText("done");
  await expect(lines.nth(1)).toContainText("Varren · status: dead · from chapter 9, The Drowned Bell");
  await lines.first().getByRole("button", { name: "Drop" }).click();
  await expect(row.getByTestId("fu-pill")).toHaveText("✓ done");
  await expect(lines.nth(1)).toContainText("dropped");
  await page.getByTestId("toast").filter({ hasText: "Dropped" }).getByRole("button", { name: "Undo" }).click();
  await expect(row.getByTestId("fu-pill")).toHaveText("1 of 2 to do");
  // Detach removes it altogether
  await lines.first().getByRole("button", { name: "Detach" }).click();
  await expect(row.getByTestId("fu-pill")).toHaveText("✓ done");
  await expect(lines).toHaveCount(1);
  // + follow-up on a line of Varren's page opens the same row; x attaches an existing planned relationship
  const knows = ((await api("GET", `${A}/relation-types`)) as unknown as Json[]).find((t) => t.label === "knows about")!;
  await api("POST", `${A}/relationships`, { type_id: knows.id, a_id: ids.Isolde, b_id: ids.Varren, standing: "planned" });
  await page.goto(`${W}/bible/${ids.Varren}`);
  const vline = page.getByTestId("entity-decisions").locator("li").filter({ hasText: DEATH });
  await vline.hover();
  await vline.getByTestId("fu-add").click();
  await expect(vline.getByTestId("followup-row")).toBeVisible();
  await page.keyboard.press("x");
  const pick = vline.getByTestId("fu-attach-form");
  await expect(pick).toContainText("Isolde knows about Varren · planned");
  await pick.getByRole("textbox").press("Enter");
  await expect(vline.getByTestId("fu-pill")).toHaveText("1 of 2 to do");
  await page.keyboard.press("Escape");
  // deleting a planned fact that follows it warns first, and leaves it dropped with its words
  await api("POST", `${A}/decisions/${d.id}/followups`, { fact: { entity_id: ids.Varren, label: "fate", value: "drowned", standing: "planned" } });
  await page.reload();
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toBe(`This follows the decision "${DEATH}". It will be listed there as dropped.`);
    void dialog.accept();
  });
  await page.getByRole("button", { name: "Remove fate" }).click();
  await expect(page.getByRole("button", { name: "Remove fate" })).toHaveCount(0);
  const list = (await api("GET", `${A}/decisions/${d.id}/followups`)) as unknown as Json[];
  expect(list.find((f) => f.what === "Varren · fate: drowned")?.state).toBe("dropped");
});

test("16.4 done when: the gap line once chapter 9 has text, Not yet, Make it canon here with the selection; nothing while typing", async () => {
  const d = await api("POST", `${A}/decisions`, { text: "Isolde leaves in chapter 9", project: "the-salt-road", entities: [ids.Isolde] });
  await api("POST", `${A}/decisions/${d.id}/followups`, {
    fact: { entity_id: ids.Isolde, label: "home", value: "gone", standing: "planned", from_chapter_id: chapters[8] } });
  const gaps = page.getByTestId("gap-line");
  await page.goto(`${W}/chapters/${chapters[8]}?panel=looseEnds`);
  await expect(page.getByTestId("findings-looseEnds")).toBeVisible();
  await expect(gaps).toHaveCount(0);
  // writing the first words makes no line appear (nothing is fetched while typing) until the chapter is opened again
  let fetched = 0;
  page.on("request", (r) => r.url().includes("/gaps") && fetched++);
  await page.getByTestId("editor").locator(".cm-content").click();
  await page.keyboard.type("Isolde was gone.");
  await expect(gaps).toHaveCount(0);
  expect(fetched).toBe(0);
  await page.waitForTimeout(2500);
  await page.reload();
  await expect(gaps).toHaveCount(1);
  await expect(gaps).toContainText("Isolde · home: gone, from this chapter · not in the book yet");
  await expect(gaps).toContainText("“Isolde leaves in chapter 9”");
  // Not yet folds it, and leaves the decision to do; Show again brings it back
  await gaps.getByTestId("gap-not-yet").click();
  await expect(gaps).toHaveCount(0);
  const later = page.getByTestId("gap-later");
  await expect(later).toContainText("Not yet · 1");
  expect((await api("GET", `${A}/decisions/${d.id}`)).followups).toEqual({ todo: 1, done: 0, dropped: 0 });
  await later.locator("summary").click();
  await later.getByTestId("gap-show-again").click();
  await expect(gaps).toHaveCount(1);
  // a sentence selected in the editor becomes the evidence
  const sentence = "Isolde was gone.";
  await page.getByTestId("editor").locator(".cm-line").filter({ hasText: sentence }).click({ clickCount: 3 });
  await gaps.hover();
  await expect(gaps.getByTestId("gap-canon")).toHaveText("Make it canon here, with the selection");
  await gaps.getByTestId("gap-canon").click();
  await expect(page.getByTestId("toast").filter({ hasText: "Canon in chapter 9" })).toContainText("the decision is done");
  await expect(gaps).toHaveCount(0);
  const isolde = await api("GET", `${A}/entities/${ids.Isolde}`);
  const home = (isolde.facts as Json[]).find((f) => f.label === "home")!;
  expect([home.standing, home.established_in_chapter_id, home.evidence]).toEqual(["canon", chapters[8], sentence]);
  expect((await api("GET", `${A}/decisions/${d.id}`)).followups).toEqual({ todo: 0, done: 1, dropped: 0 });
});

test("16.4 with Include planned: a finding on a planned row that follows a decision names it", async () => {
  const d = await api("POST", `${A}/decisions`, { text: "Varren is dead by chapter 9", project: "the-salt-road", entities: [ids.Varren] });
  await api("POST", `${A}/decisions/${d.id}/followups`, {
    fact: { entity_id: ids.Varren, label: "status", value: "dead", standing: "planned", from_chapter_id: chapters[8] } });
  await page.goto(`${W}/checks`);
  const include = page.getByTestId("include-planned");
  if (!(await include.isChecked())) await include.check();
  const found = page.getByTestId("check").filter({ hasText: "Part 10" }).or(page.getByTestId("check").filter({ hasText: "Varren" }));
  await expect(found.getByTestId("finding-decided").first()).toContainText("decided");
});

test("16.5 done when: the filter lists only decisions with open follow-ups, survives a reload; To follow through; no count in the nav", async () => {
  await page.goto(`${W}/decisions`);
  await page.getByTestId("filter-open").click();
  await expect(page).toHaveURL(/followups=open/);
  await page.reload();
  const listed = page.getByTestId("decision-list").locator("li");
  await expect(page.getByTestId("open-summary")).toContainText("open follow-up");
  for (const text of await listed.allTextContents()) expect(text).toMatch(/to do/);
  // To follow through on the front page, with "chapter 9 is written" beside the planned death
  await page.goto(W);
  const follow = page.getByTestId("follow-through");
  const cell = follow.getByTestId("follow-through-line").filter({ hasText: "Varren is dead by chapter 9" });
  await expect(cell.getByTestId("written")).toHaveText("chapter 9 is written");
  // no count in the nav
  await expect(page.locator("nav").getByText(/to do|follow-up/)).toHaveCount(0);
});

test("16.3 done when: on the phone the step is four chips and Skip, and isn't offered in airplane mode", async ({ browser }) => {
  const phone = await browser.newContext({ storageState: STATE_FILE, viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  await question("Does Isolde swim?");
  await question("Does Varren swim?");
  await p.goto(`${W}/inbox`);
  const row = p.getByTestId("inbox-list").locator("li").filter({ hasText: "Does Isolde swim?" });
  await row.locator(".item-head").click();
  await row.getByLabel(/Decision/).fill("Isolde swims like a seal");
  await row.getByRole("button", { name: "Accept" }).click();
  const step = p.getByTestId("followup-step");
  await expect(step).toBeVisible();
  for (const chip of ["fu-fact", "fu-relationship", "fu-task", "fu-attach", "fu-skip"]) await expect(step.getByTestId(chip)).toBeVisible();
  await expect(step.locator("kbd").first()).toBeHidden();
  await step.getByTestId("fu-skip").click();
  await expect(step).toHaveCount(0);
  // offline: the close goes on as it does (or not at all) and nothing is asked
  const other = p.getByTestId("inbox-list").locator("li").filter({ hasText: "Does Varren swim?" });
  await other.locator(".item-head").click();
  await other.getByLabel(/Decision/).fill("Varren never learned");
  await phone.setOffline(true);
  await other.getByRole("button", { name: "Accept" }).click();
  await p.waitForTimeout(500);
  await expect(step).toHaveCount(0);
  await phone.setOffline(false);
  await phone.close();
});
