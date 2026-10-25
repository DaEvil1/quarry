// Phase 14 on the demo world (docs/SPEC.md §16.7): its three decisions settled, done and 1 of 2 to do; chapter 3's gap
// line; and the front page's To follow through. Loads the demo world, so it runs with the other demo specs.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
let context: BrowserContext;
let page: Page;
let demo = "";

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
  await page.goto("/");
  demo = (await api("POST", "/api/worlds/demo")).slug;
});

test.afterAll(async () => {
  if (demo) await api("DELETE", `/api/worlds/${demo}`, { name: "The Ninefold Delta (demo)" }).catch(() => undefined);
  await context.close();
});

test("16.7 done when: the demo's decisions settled, done and 1 of 2 to do; chapter 3's gap line; To follow through", async () => {
  await page.goto(`/w/${demo}/decisions`);
  const line = (text: string) => page.getByTestId("decision-list").locator("li").filter({ hasText: text });
  await expect(line("Oskar dies in chapter 2")).toBeVisible();
  await expect(line("Oskar dies in chapter 2").getByTestId("fu-pill")).toHaveCount(0);
  await expect(line("Hesper is a cartographer").getByTestId("fu-pill")).toHaveText("✓ done");
  await expect(line("Brother Cade dies at Saltreach").getByTestId("fu-pill")).toHaveText("1 of 2 to do");

  await page.goto(`/w/${demo}`);
  const follow = page.getByTestId("follow-through-line");
  await expect(follow).toHaveCount(1);
  await expect(follow).toContainText("Brother Cade dies at Saltreach, in What the River Kept");
  await follow.getByTestId("written").click();
  const gap = page.getByTestId("gap-line");
  await expect(gap).toContainText("Brother Cade · status: dead, from this chapter · not in the book yet");
  await expect(gap).toContainText("“Brother Cade dies at Saltreach, in What the River Kept”");
});
