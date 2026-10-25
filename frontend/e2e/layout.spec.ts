// The pages hold together at every width (docs/DECISIONS.md, "Page widths" and "Labels never cut off"): on the demo
// world, at a phone's width, a laptop's, a wide screen's and a very wide one's, no page scrolls sideways; reading pages
// sit in the middle and the drawn views use the width; names on the Timeline, the Graph and the Chart never sit on
// one another or run off the edge; the Timeline says it is empty only when it is; Where everyone is keeps its chapters
// in one row. Runs after phase 1 in its signed-in state; the demo world it loads is deleted at the end.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
let context: BrowserContext;
let page: Page;
let demo = "";

const WIDTHS = [
  { name: "phone", width: 390, height: 844 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "wide", width: 1920, height: 1080 },
  { name: "very wide", width: 2560, height: 1440 },
];

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
  const r = await page.request.post("/api/worlds/demo", { headers: { Origin: BASE } });
  expect(r.ok()).toBeTruthy();
  demo = (await r.json()).slug;
});

test.afterAll(async () => {
  if (demo) await page.request.delete(`/api/worlds/${demo}`, { data: { name: "The Ninefold Delta (demo)" }, headers: { Origin: BASE } }).catch(() => undefined);
  await context.close();
});

/** Pairs of the matching elements whose boxes overlap (by more than a pixel), as "a / b", for the message. */
async function overlapping(selector: string, within?: string): Promise<string[]> {
  return page.evaluate(([sel, scope]) => {
    const groups = scope ? [...document.querySelectorAll(scope)] : [document.body];
    const out: string[] = [];
    for (const g of groups) {
      const els = [...g.querySelectorAll(sel)].map((e) => ({ e, r: e.getBoundingClientRect() })).filter((x) => x.r.width > 0);
      for (let i = 0; i < els.length; i++) {
        for (let j = i + 1; j < els.length; j++) {
          const a = els[i]!.r;
          const b = els[j]!.r;
          if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) out.push(`${els[i]!.e.textContent} / ${els[j]!.e.textContent}`);
        }
      }
    }
    return out;
  }, [selector, within ?? ""] as const);
}

/** The matching elements that reach outside the container's box. */
async function outside(selector: string, container: string): Promise<string[]> {
  return page.evaluate(([sel, box]) => {
    const c = document.querySelector(box)!.getBoundingClientRect();
    return [...document.querySelectorAll(sel)]
      .filter((e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && (r.left < c.left - 1 || r.right > c.right + 1 || r.top < c.top - 1 || r.bottom > c.bottom + 1);
      })
      .map((e) => e.textContent ?? "");
  }, [selector, container] as const);
}

async function noSidewaysScroll(what: string) {
  const { scroll, inner } = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
  expect(scroll, `${what} scrolls sideways`).toBeLessThanOrEqual(inner + 1);
}

const PAGES = ["", "/journal", "/bible/k/character", "/bible/k/event", "/bible/k/place", "/bible/labels", "/checks", "/names", "/inbox", "/triage", "/settings", "/graph", "/chart", "/timeline", "/where"];

for (const w of WIDTHS) {
  test(`at ${w.name} width (${w.width}px) the pages hold together`, async () => {
    await page.setViewportSize({ width: w.width, height: w.height });
    for (const p of PAGES) {
      await page.goto(`/w/${demo}${p}`);
      await expect(page.locator("main h1").first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      await noSidewaysScroll(p || "the front page");
    }

    // reading pages sit in the middle of what the nav leaves; drawn views and tables use the width
    if (w.width >= 1920) {
      await page.goto(`/w/${demo}/journal`);
      await expect(page.locator("main h1").first()).toBeVisible();
      const read = await page.evaluate(() => {
        const m = document.querySelector("main")!.getBoundingClientRect();
        const p = document.querySelector("main > .page")!.getBoundingClientRect();
        return { left: p.left - m.left, right: m.right - p.right };
      });
      expect(Math.abs(read.left - read.right), "a reading page sits in the middle").toBeLessThan(4);
      for (const p of ["/timeline", "/chart", "/graph", "/where", "/bible/k/character"]) {
        await page.goto(`/w/${demo}${p}`);
        await expect(page.locator("main h1").first()).toBeVisible();
        const share = await page.evaluate(() => document.querySelector("main > .page")!.getBoundingClientRect().width / document.querySelector("main")!.clientWidth);
        expect(share, `${p} uses the width`).toBeGreaterThan(p.startsWith("/bible") && w.width > 2000 ? 0.7 : 0.85);
      }
    }

    // the Timeline: names in rows, never on one another or past the edge; ticks and era names whole; not "empty"
    await page.goto(`/w/${demo}/timeline`);
    await expect(page.getByTestId("mark").first()).toBeVisible();
    await expect(page.getByTestId("timeline-empty")).toHaveCount(0);
    await expect(page.getByTestId("mark-label").first()).toBeVisible();
    expect(await overlapping('[data-testid="mark-label"]', '[data-testid="lane"]'), "Timeline names overlap").toEqual([]);
    expect(await outside('[data-testid="mark-label"], [data-testid="tick-label"], [data-testid="era-name"]', '[data-testid="timeline"]'), "Timeline text cut off").toEqual([]);
    expect(await overlapping('[data-testid="tick-label"], [data-testid="era-name"]'), "era names on the axis numbers").toEqual([]);
    // what is outside time is listed under the Timeline, not drawn over the lanes
    await expect(page.getByTestId("outside-strip")).toContainText("The Opening of the Hand");
    await expect(page.getByTestId("lane-outside").first()).toHaveText(/^\d+ outside time/);

    // the Graph's names
    await page.goto(`/w/${demo}/graph`);
    await expect(page.getByTestId("graph-label").first()).toBeVisible();
    expect(await overlapping('[data-testid="graph-label"]'), "Graph names overlap").toEqual([]);

    // the Chart's names: none on another, none past the edge
    await page.goto(`/w/${demo}/chart`);
    await expect(page.getByTestId("chart-name").first()).toBeVisible();
    await page.waitForTimeout(600);
    expect(await overlapping('[data-testid="chart-name"]'), "Chart names overlap").toEqual([]);
    expect(await outside('[data-testid="chart-name"]', '[data-testid="chart"]'), "Chart names cut off").toEqual([]);

    // Where everyone is: every chapter's heading in the one row
    await page.goto(`/w/${demo}/where`);
    const heads = page.locator("th.chapter-head");
    await expect(heads.first()).toBeVisible();
    const tops = await heads.evaluateAll((els) => [...new Set(els.map((e) => Math.round(e.getBoundingClientRect().top)))]);
    expect(tops, "chapter headings in one row").toHaveLength(1);
  });
}

test("the Characters table reads a birth recorded by its time, and a species on one line", async () => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`/w/${demo}/bible/k/character`);
  const tamsin = page.locator("tr", { has: page.getByRole("link", { name: "Tamsin Vey", exact: true }) });
  await expect(tamsin.getByTestId("fact-time")).toHaveText("year 395");
  const cade = page.locator("tr", { has: page.getByRole("link", { name: "Brother Cade", exact: true }) });
  const species = cade.getByRole("button", { name: "marsh-wight" });
  const h = await species.evaluate((e) => e.getBoundingClientRect().height);
  expect(h, "marsh-wight on one line").toBeLessThan(24);
});
