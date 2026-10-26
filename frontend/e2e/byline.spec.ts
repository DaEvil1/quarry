// Phase 17: a byline (docs/SPEC.md §19). Set in the project's Edit form, shown under the title on the project page and
// the Read page, and cleared again. Builds a world of its own.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

test("19 done when: a byline set in the Edit form shows under the title, when reading too, and clears", async () => {
  await page.goto("/");
  const h = { Origin: BASE };
  expect((await page.request.post("/api/worlds", { data: { name: "The Byline Coast" }, headers: h })).ok()).toBeTruthy();
  expect((await page.request.post("/api/worlds/the-byline-coast/projects", { data: { name: "The Salt Road" }, headers: h })).ok()).toBeTruthy();
  await page.request.post("/api/worlds/the-byline-coast/projects/the-salt-road/chapters", { data: { title: "One", body: "Isolde waits." }, headers: h });

  await page.goto("/w/the-byline-coast/p/the-salt-road");
  await expect(page.getByTestId("byline")).toHaveCount(0);
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Byline").fill("A Salt Road Tale");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("byline")).toHaveText("A Salt Road Tale");
  await page.goto("/w/the-byline-coast/p/the-salt-road/read");
  await expect(page.getByTestId("read-byline")).toHaveText("A Salt Road Tale");

  await page.goto("/w/the-byline-coast/p/the-salt-road");
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Byline").fill("");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByTestId("byline")).toHaveCount(0);
});
