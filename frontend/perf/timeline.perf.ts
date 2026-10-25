// The Timeline's budget (docs/SPEC.md §13.2.6) against a running Quarry with an empty database (run this file on its
// own: `npx playwright test -c playwright.perf.config.ts timeline`). Seeds a made-up world of 3,000 events over 3,400
// years (most in a few busy stretches, at fractions of a year), eight eras (two nested), 150 characters with birth
// times and some taking part, and a book of 20 chapters set in years 400–419. Then measures what moving around feels
// like: the first drawing, zooming in from the whole world to one year and back out (frames, and that clusters split
// into named marks and merge again), panning by dragging, and the same at 4× slower CPU; and checks that no more than
// a few hundred marks are drawn at any zoom. Writes perf-timeline.json and prints a table.

import { writeFileSync } from "node:fs";

import { expect, test, type CDPSession, type Page } from "@playwright/test";

const SETUP_TOKEN = process.env.PERF_SETUP_TOKEN ?? "local-setup-token";
const EVENTS = Number(process.env.PERF_EVENTS ?? 3000);
const BASE = process.env.PERF_BASE_URL ?? "http://localhost:8766";
const headers = { Origin: BASE };

test.describe.configure({ mode: "serial" });
test.setTimeout(Number(process.env.PERF_TIMEOUT ?? 900_000));

let page: Page;
let cdp: CDPSession;
const results: Record<string, number | string> = {};
const W = "/w/perf-timeline";
const api = "/api/worlds/perf-timeline";

let seed = 7;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const SYL = ["ar", "bel", "cor", "dan", "el", "fen", "gar", "hal", "is", "jor", "kel", "lan", "mor", "nes", "or", "pel", "quin", "ros", "sel", "tor", "ul", "var", "wen", "yr", "zan"];
const word = (n = 2) => {
  const w = Array.from({ length: n }, () => SYL[Math.floor(rnd() * SYL.length)]).join("");
  return w[0]!.toUpperCase() + w.slice(1);
};
const pct = (xs: number[], p: number) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? Math.round(s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))]! * 10) / 10 : 0;
};
const started = Date.now();
const log = (msg: string) => console.log(`[${((Date.now() - started) / 1000).toFixed(1)}s] ${msg}`);

// seeding runs several requests at once; the server can refuse one that races another (a deadlock, a label made
// twice), so a failed one is tried again
async function call(method: string, url: string, data?: unknown) {
  for (let attempt = 0; ; attempt++) {
    const r = await page.request.fetch(url, { method, data, headers });
    if (r.ok()) return r.status() === 204 ? {} : r.json();
    if (attempt >= 3 || r.status() < 500) throw new Error(`${method} ${url}: ${r.status()} ${await r.text()}`);
    await new Promise((res) => setTimeout(res, 200 * (attempt + 1)));
  }
}
/** run `fn` over `xs`, `n` at a time */
async function pool<T>(xs: T[], n: number, fn: (x: T) => Promise<unknown>) {
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => {
    while (i < xs.length) await fn(xs[i++]!);
  }));
}
async function entity(name: string, kind: string, when?: Record<string, unknown>) {
  const e = await call("POST", `${api}/entities`, { name, kind });
  if (when) await call("PATCH", `${api}/entities/${e.id}`, { base_version: e.version, ...when });
  return e as { id: string; version: number };
}

// frames: the time between animation frames while something moves, and how many marks are drawn
const FRAMES = `
window.__frames = []; window.__drawn = 0;
window.__watch = () => {
  window.__frames = []; window.__drawn = 0; window.__watching = true;
  let last = performance.now();
  const tick = (t) => {
    if (!window.__watching) return;
    window.__frames.push(t - last); last = t;
    window.__drawn = Math.max(window.__drawn, document.querySelectorAll('[data-testid="mark"], [data-testid="cluster"]').length);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};
window.__stop = () => { window.__watching = false; return { frames: window.__frames.slice(1), drawn: window.__drawn }; };
`;

async function measure(label: string, fn: () => Promise<void>) {
  await page.evaluate(() => (window as unknown as { __watch: () => void }).__watch());
  await fn();
  const { frames, drawn } = await page.evaluate(() => (window as unknown as { __stop: () => { frames: number[]; drawn: number } }).__stop());
  results[`${label} frame p95 ms`] = pct(frames, 95);
  results[`${label} frame max ms`] = pct(frames, 100);
  results[`${label} most drawn`] = drawn;
  return { frames, drawn };
}

const svg = () => page.getByTestId("timeline");
const counts = () => page.evaluate(() => ({
  marks: document.querySelectorAll('[data-testid="mark"]').length,
  named: document.querySelectorAll('[data-testid="mark"] .tl-label').length,
  clusters: document.querySelectorAll('[data-testid="cluster"]').length,
}));

async function zoom(steps: number, dy: number) {
  const b = (await svg().boundingBox())!;
  await page.mouse.move(b.x + b.width * 0.5, b.y + b.height * 0.6);
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, dy);
    await page.waitForTimeout(16);
  }
  await page.waitForTimeout(100);
}

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  await page.addInitScript(FRAMES);
  cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
});

test.afterAll(async () => {
  writeFileSync("perf-timeline.json", JSON.stringify(results, null, 2));
  console.table(results);
  await page.close();
});

test("set up and seed 3,000 events", async () => {
  await page.goto("/");
  await page.getByLabel("Setup token").fill(SETUP_TOKEN);
  await page.getByLabel("Your name").fill("Perf Writer");
  await page.getByLabel("Name for this device's passkey").fill("Perf");
  await page.getByRole("button", { name: "Create passkey" }).click();
  await page.getByTestId("codes-saved").click();
  await page.getByLabel("World name").fill("Perf Timeline");
  await page.getByLabel("First project").fill("Long Book");
  await page.getByRole("button", { name: "Create world" }).click();
  await expect(page).toHaveURL(/\/p\/long-book$/);

  // eras, two nested
  const eras: [string, number, number | null][] = [
    ["the First Dark", -3000, -2200], ["the Kindling", -2200, -1400], ["the Long Ebb", -1400, -600], ["the Low Tide", -1100, -900],
    ["the Lamp Years", -600, 200], ["the Bright Watch", -100, 60], ["the Salt Age", 200, null], ["the Drowned Years", 380, 395],
  ];
  for (const [name, at, end] of eras) {
    const e = await entity(name, "event", { time_at: at, time_end: end });
    await call("POST", `${api}/entities/${e.id}/facts`, { label: "type", value: "era" });
  }
  // the book: 20 chapters in years 400–419
  for (let n = 0; n < 20; n++) {
    const ch = await call("POST", `${api}/projects/long-book/chapters`, { title: `Chapter ${n + 1}`, body: "The lamps were lit along the wall.\n" });
    await call("PATCH", `${api}/chapters/${ch.id}/about`, { time_at: 400 + n });
  }
  // characters with birth times
  const names = new Set<string>();
  const people: { id: string }[] = [];
  await pool(Array.from({ length: 150 }, (_, i) => i), 8, async () => {
    let name = `${word()} ${word()}`;
    while (names.has(name)) name += ` ${word(1)}`;
    names.add(name);
    const e = await entity(name, "character");
    await call("POST", `${api}/entities/${e.id}/facts`, { label: "born", value: "", from_time: Math.round(-3000 + rnd() * 3380) });
    people.push(e);
  });
  log("eras, book and characters");
  // 3,000 events: 70% in six busy stretches, the rest spread out; at fractions of a year
  const busy = [-2500, -1700, -950, -300, 30, 385];
  const times = Array.from({ length: EVENTS }, () => {
    if (rnd() < 0.7) return Math.round((busy[Math.floor(rnd() * busy.length)]! + (rnd() - 0.5) * 40) * 100) / 100;
    return Math.round((-3000 + rnd() * 3420) * 100) / 100;
  });
  const events: { id: string }[] = [];
  let made = 0;
  const t0 = Date.now();
  await pool(times.map((t, i) => [t, i] as const), 16, async ([t, i]) => {
    let name = `The ${word()} ${["Flood", "Fire", "Treaty", "Founding", "Wreck", "Crossing", "Feast", "Siege"][i % 8]}`;
    while (names.has(name)) name += ` ${word(1)}`;
    names.add(name);
    events.push(await entity(name, "event", { time_at: t }));
    if (++made % 500 === 0) log(`${made} events`);
  });
  results["seed events s"] = Math.round((Date.now() - t0) / 1000);
  // some taking part
  const types = (await call("GET", `${api}/relation-types`)) as { id: string; label: string; a_kind: string; b_kind: string }[];
  const involved = types.find((t) => /involved|took part/.test(t.label) && (t.a_kind === "character" || t.b_kind === "character")) ?? types.find((t) => t.label === "linked to")!;
  await pool(events.slice(0, 300), 12, async (e) => {
    const p = people[Math.floor(rnd() * people.length)]!;
    const [a, b] = involved.a_kind === "event" ? [e.id, p.id] : [p.id, e.id];
    await call("POST", `${api}/relationships`, { type_id: involved.id, a_id: a, b_id: b });
  });
  results["events"] = events.length;
  log("seeded");
});

test("the Timeline with 3,000 events", async () => {
  // the first drawing
  const t0 = Date.now();
  await page.goto(`${W}/timeline`);
  await expect(svg().locator('[data-testid="cluster"], [data-testid="mark"]').first()).toBeVisible({ timeout: 30_000 });
  results["first drawing ms (page open)"] = Date.now() - t0;
  // again, with the cards already on the device: the Timeline's own share
  await page.goto(`${W}/graph`);
  const t1 = Date.now();
  await page.getByTestId("nav-timeline").click();
  await expect(svg().locator('[data-testid="cluster"], [data-testid="mark"]').first()).toBeVisible();
  results["first drawing ms (from the nav)"] = Date.now() - t1;
  // furthest out: clusters with counts, a few hundred things drawn at most
  const out = await counts();
  results["fit: clusters"] = out.clusters;
  results["fit: drawn"] = out.marks + out.clusters;
  expect(out.clusters).toBeGreaterThan(0);
  expect(out.marks + out.clusters).toBeLessThan(400);

  // zooming in to about a year: the clusters split into named marks
  await measure("desk: zoom in", () => zoom(40, -250));
  const near = await counts();
  results["one year: named marks"] = near.named;
  results["one year: clusters"] = near.clusters;
  expect(near.named).toBeGreaterThan(0);
  // panning by dragging
  const b = (await svg().boundingBox())!;
  await measure("desk: pan", async () => {
    await page.mouse.move(b.x + b.width * 0.8, b.y + b.height * 0.7);
    await page.mouse.down();
    for (let i = 0; i < 40; i++) await page.mouse.move(b.x + b.width * (0.8 - i * 0.015), b.y + b.height * 0.7);
    await page.mouse.up();
  });
  // and back out: they merge again
  await measure("desk: zoom out", () => zoom(40, 250));
  const back = await counts();
  expect(back.clusters).toBeGreaterThan(0);

  // the same at phone speed
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await measure("4× CPU: zoom in", () => zoom(30, -300));
  await measure("4× CPU: pan", async () => {
    await page.mouse.move(b.x + b.width * 0.8, b.y + b.height * 0.7);
    await page.mouse.down();
    for (let i = 0; i < 30; i++) await page.mouse.move(b.x + b.width * (0.8 - i * 0.02), b.y + b.height * 0.7);
    await page.mouse.up();
  });
  await measure("4× CPU: zoom out", () => zoom(30, 300));
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });

  // the budget (DECISIONS, 2026-10-22): 60 frames a second on the desk, nothing over 50 ms at 4× slower CPU, the first
  // drawing within a second. Frame times are reported; only gross misses fail the run, since a shared CI machine is noisy.
  for (const k of ["desk: zoom in", "desk: pan", "desk: zoom out"]) expect(Number(results[`${k} frame p95 ms`])).toBeLessThan(34);
  for (const k of ["4× CPU: zoom in", "4× CPU: pan", "4× CPU: zoom out"]) expect(Number(results[`${k} frame p95 ms`])).toBeLessThan(100);
  for (const k of Object.keys(results).filter((x) => x.endsWith("most drawn"))) expect(Number(results[k])).toBeLessThan(500);
});

// With PERF_SHOTS=<folder>: the Timeline with all of it, at desk and phone width.
test("screenshots", async () => {
  const dir = process.env.PERF_SHOTS;
  test.skip(!dir, "PERF_SHOTS not set");
  for (const [w, h, tag] of [[1400, 900, "desk"], [390, 844, "phone"]] as const) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`${W}/timeline`);
    await expect(svg()).toBeVisible();
    await page.screenshot({ path: `${dir}/${tag}-timeline-3000.png` });
  }
});
