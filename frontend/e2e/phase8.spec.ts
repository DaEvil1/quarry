// Phase 8: views. The relationship graph centred on someone (who they know directly and through one other), colour
// by cluster, the place tree with who is where as of a chapter, and the cast per chapter on the manuscript page.
// Carries on from the earlier specs (Varren parent of Isolde, lives in Old Harbour, member of the Lamp Guild; Isolde
// visits Old Harbour and is at it in "Night watch"; Brannoch is a character).

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const W = "/w/grey-shore";
let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

test("the graph centred on someone: who they know directly, and through one other", async () => {
  // Isolde knows Brannoch, whom Varren doesn't
  await page.goto(`${W}/bible`);
  await page.getByTestId("bible-list").getByRole("link", { name: "Isolde", exact: true }).click();
  const rel = page.getByTestId("relationships");
  await rel.getByLabel("Bible entry").fill("Brannoch");
  await page.keyboard.press("Enter");
  await rel.getByLabel("How they\'re connected").selectOption({ label: "friend of" });
  await rel.getByLabel("New relationship standing").selectOption("canon");
  await rel.getByRole("button", { name: "Add", exact: true }).click();
  await expect(rel.locator("dl")).toContainText("Brannoch");

  await page.locator(".nav").getByTestId("nav-graph").click();
  const graph = page.getByTestId("graph");
  await expect(graph.locator(".gnode")).not.toHaveCount(0);
  await graph.locator(".gnode[data-name='Varren']").click();
  const circle = page.getByTestId("circle");
  await expect(circle.getByTestId("circle-direct")).toContainText("Isolde");
  await expect(circle.getByTestId("circle-direct")).toContainText("parent of");
  await expect(circle.getByTestId("circle-direct")).toContainText("Lamp Guild");
  await expect(circle.getByTestId("circle-second")).toContainText("Brannoch");
  await expect(circle.getByTestId("circle-second")).toContainText("via Isolde");
  // only the neighbourhood is drawn
  await expect(graph.locator(".gnode[data-name='Brannoch']")).toHaveCount(1);
  await page.getByLabel("How far").selectOption({ label: "direct links" });
  await expect(graph.locator(".gnode[data-name='Brannoch']")).toHaveCount(0);

  await page.getByRole("button", { name: "Everyone" }).click();
  await page.getByLabel("Colour by").selectOption("cluster");
  await expect(page.getByTestId("cluster-count")).toContainText("cluster");
});

test("the place tree, with who lives there and who is there as of a chapter", async () => {
  await page.getByTestId("tab-places").click();
  const harbour = page.getByTestId("place-Old Harbour");
  await expect(harbour).toContainText("home of: Varren");
  await expect(harbour).not.toContainText("here now");
  await page.getByTestId("graph-as-of").selectOption({ label: "Night watch" });
  await expect(harbour).toContainText("here now:");
  await expect(harbour).toContainText("Isolde");
});

test("the manuscript lists the cast of each chapter", async () => {
  await page.goto(`${W}/p/first-light`);
  const row = page.getByTestId("chapters").locator("li", { hasText: "Night watch" });
  const cast = row.getByTestId("cast");
  await expect(cast).toContainText("Varren");
  await expect(cast).toContainText("Old Harbour");
  await expect(cast.locator(".k-place")).toHaveText(["Old Harbour"]);
});
