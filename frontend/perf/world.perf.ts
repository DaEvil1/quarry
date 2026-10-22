// Performance check against a running Quarry with an empty database (see docs/development.md, "Performance").
// Seeds a large synthetic world (no real story text): a few hundred bible entries with other names, facts and
// relationships, and a 10,000-word chapter full of their names. Then measures what a writer feels: how fast the
// chapter opens, how long a keystroke takes to show at desk speed and at phone speed (CPU slowed 4×), scrolling, a
// save, and the bible pages. Writes perf-results.json and prints a table.

import { writeFileSync } from "node:fs";

import { expect, test, type APIRequestContext, type CDPSession, type Page } from "@playwright/test";

const SETUP_TOKEN = process.env.PERF_SETUP_TOKEN ?? "local-setup-token";
const ENTRIES = Number(process.env.PERF_ENTRIES ?? 400);
const WORDS = Number(process.env.PERF_WORDS ?? 10_000);
const BASE = process.env.PERF_BASE_URL ?? "http://localhost:8766";
// the API refuses writes without the app's own Origin (its CSRF guard)
const headers = { Origin: BASE };

test.describe.configure({ mode: "serial" });
test.setTimeout(Number(process.env.PERF_TIMEOUT ?? 600_000));

let page: Page;
let cdp: CDPSession;
const results: Record<string, number | string> = {};
const W = "/w/perf-world";
const api = `/api/worlds/perf-world`;

// ---- synthetic material ------------------------------------------------------------------------------------
let seed = 42;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const pick = <T>(xs: T[]) => xs[Math.floor(rnd() * xs.length)]!;
const SYL = ["ar", "bel", "cor", "dan", "el", "fen", "gar", "hal", "is", "jor", "kel", "lan", "mor", "nes", "or", "pel",
  "quin", "ros", "sel", "tor", "ul", "var", "wen", "yr", "zan", "brae", "cath", "drem", "eth", "fal"];
const cap = (s: string) => s[0]!.toUpperCase() + s.slice(1);
const word = (n = 2 + Math.floor(rnd() * 2)) => cap(Array.from({ length: n }, () => pick(SYL)).join(""));
const PROSE = ("the of and to a in was he she it that with as his her on for at by from had but they not were said " +
  "into over light sea wind harbour stone road door window night morning boat rope lamp tide long slow cold grey " +
  "walked looked turned waited listened remembered carried opened closed watched").split(" ");
const sentence = (names: string[]) => {
  const n = 8 + Math.floor(rnd() * 14);
  const words = Array.from({ length: n }, () => pick(PROSE));
  if (rnd() < 0.8) words.splice(Math.floor(rnd() * n), 0, pick(names));
  if (rnd() < 0.3) words.splice(Math.floor(rnd() * n), 0, pick(names));
  const s = words.join(" ");
  return cap(s) + ".";
};

const pct = (xs: number[], p: number) => {
  const s = [...xs].sort((a, b) => a - b);
  return Math.round(s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))]! * 10) / 10;
};

const started = Date.now();
const log = (msg: string) => console.log(`[${((Date.now() - started) / 1000).toFixed(1)}s] ${msg}`);

async function timed<T>(fn: () => Promise<T>): Promise<[T, number]> {
  const t = performance.now();
  const out = await fn();
  return [out, performance.now() - t];
}

async function postJson(r: APIRequestContext, url: string, data: unknown) {
  const res = await r.post(url, { data, headers });
  if (!res.ok()) throw new Error(`${url}: ${res.status()} ${await res.text()}`);
  return res.json();
}

// ---- in-page measurement: how long from a key press to the frame that shows it -----------------------------------
// Chrome's Event Timing (the basis of the INP metric) reports every key whose press-to-paint took 16 ms or more,
// grouped by interaction; keys it doesn't report were faster than that.
const LATENCY = `
window.__keys = new Map();
new PerformanceObserver((l) => {
  for (const e of l.getEntries()) {
    if (!e.interactionId) continue;
    window.__keys.set(e.interactionId, Math.max(window.__keys.get(e.interactionId) || 0, e.duration));
  }
}).observe({ type: "event", durationThreshold: 16, buffered: true });
window.__long = [];
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long.push(e.duration); }).observe({ type: "longtask" });
`;

interface ProfileNode { id: number; callFrame: { functionName: string; url: string; lineNumber: number }; children?: number[] }

/** With PERF_PROFILE=1: where the time went while typing, by function (self time). */
async function topFunctions(profile: { nodes: ProfileNode[]; samples: number[]; timeDeltas: number[] }) {
  const self = new Map<number, number>();
  profile.samples.forEach((id, i) => self.set(id, (self.get(id) ?? 0) + (profile.timeDeltas[i] ?? 0)));
  const byName = new Map<string, number>();
  for (const n of profile.nodes) {
    const f = n.callFrame;
    const key = `${f.functionName || "(anon)"} ${f.url.split("/").pop()}:${f.lineNumber}`;
    byName.set(key, (byName.get(key) ?? 0) + (self.get(n.id) ?? 0) / 1000);
  }
  return [...byName.entries()].filter(([k]) => !k.startsWith("(idle)") && !k.startsWith("(program)")).sort((a, b) => b[1] - a[1]).slice(0, 15);
}

async function typeAndMeasure(label: string, text: string) {
  await page.evaluate(() => (window as unknown as { __keys: Map<number, number> }).__keys.clear());
  const profiling = process.env.PERF_PROFILE === "1";
  if (profiling) {
    await cdp.send("Profiler.enable");
    await cdp.send("Profiler.setSamplingInterval", { interval: 200 });
    await cdp.send("Profiler.start");
  }
  await page.keyboard.type(text, { delay: 60 });
  if (profiling) {
    const { profile } = await cdp.send("Profiler.stop");
    console.log(`
${label}: top functions by self time (ms)`);
    for (const [k, ms] of await topFunctions(profile as never)) console.log(`  ${ms.toFixed(1).padStart(7)}  ${k}`);
  }
  await page.waitForTimeout(500);
  const slow = await page.evaluate(() => [...(window as unknown as { __keys: Map<number, number> }).__keys.values()]);
  // every key is one interaction; the ones not reported took under 16 ms
  const all = [...slow, ...Array<number>(Math.max(0, text.length - slow.length)).fill(16)];
  results[`${label} p50 ms`] = pct(all, 50);
  results[`${label} p95 ms`] = pct(all, 95);
  results[`${label} max ms`] = pct(all, 100);
  results[`${label} keys over 50 ms`] = slow.filter((d) => d > 50).length;
}

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await page.addInitScript(LATENCY);
  cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
});

test.afterAll(async () => {
  writeFileSync("perf-results.json", JSON.stringify(results, null, 2));
  console.table(results);
  await page.close();
});

test("set up and seed a large world", async () => {
  await page.goto("/");
  await page.getByLabel("Setup token").fill(SETUP_TOKEN);
  await page.getByLabel("Your name").fill("Perf Writer");
  await page.getByLabel("Name for this device's passkey").fill("Perf");
  await page.getByRole("button", { name: "Create passkey" }).click();
  await page.getByTestId("codes-saved").click();
  await page.getByLabel("World name").fill("Perf World");
  await page.getByLabel("First project").fill("Long Book");
  await page.getByRole("button", { name: "Create world" }).click();
  await expect(page).toHaveURL(/\/p\/long-book$/);

  const r = page.request;
  const kinds = [
    ...Array<string>(Math.round(ENTRIES * 0.7)).fill("character"),
    ...Array<string>(Math.round(ENTRIES * 0.15)).fill("place"),
    ...Array<string>(Math.round(ENTRIES * 0.08)).fill("faction"),
    ...Array<string>(Math.round(ENTRIES * 0.07)).fill("object"),
  ];
  const used = new Set<string>();
  const entities: { id: string; name: string; kind: string }[] = [];
  const createMs: number[] = [];
  for (const kind of kinds) {
    let name = kind === "character" ? `${word()} ${word()}` : kind === "place" ? `${pick(["Old", "North", "Grey", "Low"])} ${word()}` : `The ${word()} ${pick(["Guild", "Circle", "Hand", "Stone", "Crown"])}`;
    while (used.has(name)) name += " " + word(1);
    used.add(name);
    const aliases = rnd() < 0.3 ? [word()] : [];
    const [e, ms] = await timed(() => postJson(r, `${api}/entities`, { name, kind, aliases }));
    createMs.push(ms);
    entities.push({ id: e.id, name, kind });
  }
  results["entries"] = entities.length;
  log("entries created");
  results["create entry p50 ms"] = pct(createMs, 50);
  results["create entry p95 ms"] = pct(createMs, 95);

  // facts on a third of them, three each
  const factMs: number[] = [];
  for (const e of entities.filter((_, i) => i % 3 === 0)) {
    for (const [label, value] of [["eye colour", pick(["grey", "brown", "green"])], ["age", String(20 + Math.floor(rnd() * 50))], ["voice", "low"]]) {
      const [, ms] = await timed(() => postJson(r, `${api}/entities/${e.id}/facts`, { label, value }));
      factMs.push(ms);
    }
  }
  results["add fact p50 ms"] = pct(factMs, 50);
  log("facts added");

  // relationships: a character–character web plus memberships
  const types = (await (await r.get(`${api}/relation-types`)).json()) as { id: string; a_kind: string; b_kind: string; label: string }[];
  const cc = types.filter((t) => t.a_kind === "character" && t.b_kind === "character");
  const member = types.find((t) => t.label === "member of")!;
  const chars = entities.filter((e) => e.kind === "character");
  const factions = entities.filter((e) => e.kind === "faction");
  const relMs: number[] = [];
  for (let i = 0; i < ENTRIES * 1.5; i++) {
    const a = pick(chars);
    let b = pick(chars);
    if (a.id === b.id) b = chars[(chars.indexOf(a) + 1) % chars.length]!;
    const [, ms] = await timed(() => postJson(r, `${api}/relationships`, { type_id: pick(cc).id, a_id: a.id, b_id: b.id }));
    relMs.push(ms);
  }
  for (const c of chars.slice(0, Math.floor(chars.length / 2))) {
    await postJson(r, `${api}/relationships`, { type_id: member.id, a_id: c.id, b_id: pick(factions).id });
  }
  results["add relationship p50 ms"] = pct(relMs, 50);
  log("relationships added");

  // the long chapter: names everywhere, the odd misspelling
  const names = entities.map((e) => e.name);
  const paras: string[] = [];
  let words = 0;
  while (words < WORDS) {
    const p = Array.from({ length: 4 + Math.floor(rnd() * 5) }, () => sentence(names)).join(" ");
    words += p.split(/\s+/).length;
    paras.push(rnd() < 0.05 ? p.replace(/\b([A-Z][a-z]{5,})\b/, (m) => m.slice(0, -2) + m.slice(-1)) : p);
  }
  const body = paras.join("\n\n");
  const [ch, chMs] = await timed(() => postJson(r, `${api}/projects/long-book/chapters`, { title: "The long one", body }));
  results["chapter words"] = words;
  log("chapter created");
  results["create 10k chapter ms"] = Math.round(chMs);
  const [res, saveMs] = await timed(() => r.patch(`${api}/chapters/${ch.id}`, { data: { base_version: ch.version, body: body + " One more." }, headers }));
  expect(res.ok()).toBeTruthy();
  results["save 10k chapter ms"] = Math.round(saveMs);
  results["chapter id"] = ch.id;
  for (const title of ["The second", "The third"]) {
    await postJson(r, `${api}/projects/long-book/chapters`, { title, body: paras.slice(0, 40).reverse().join("\n\n") });
  }

  const [cardsRes, cardsMs] = await timed(() => r.get(`${api}/cards`));
  results["cards ms"] = Math.round(cardsMs);
  results["cards kB"] = Math.round((await cardsRes.body()).length / 1024);
  log("seeded");
});

test("bible pages", async () => {
  let [, ms] = await timed(async () => {
    await page.goto(`${W}/bible`);
    await expect(page.getByTestId("bible-list").first()).toBeVisible();
  });
  results["bible page ms"] = Math.round(ms);
  [, ms] = await timed(async () => {
    await page.goto(`${W}/bible/k/character`);
    await expect(page.getByTestId("bible-list").locator("tbody tr").first()).toBeVisible();
  });
  results["characters table ms"] = Math.round(ms);
  [, ms] = await timed(async () => {
    await page.getByTestId("bible-list").locator("tbody tr a").first().click();
    await expect(page.getByTestId("relationships")).toBeVisible();
    await expect(page.getByTestId("mentions")).toBeVisible();
  });
  results["entry page ms"] = Math.round(ms);
  [, ms] = await timed(async () => {
    await page.goto(`${W}/where`);
    await expect(page.getByTestId("where-grid")).toBeVisible();
  });
  results["where everyone is ms"] = Math.round(ms);
});

test("the editor with a long chapter", async () => {
  const id = results["chapter id"];
  const [, openMs] = await timed(async () => {
    await page.goto(`${W}/chapters/${id}`);
    await expect(page.getByTestId("editor").locator(".cm-name").first()).toBeVisible();
  });
  results["open chapter ms"] = Math.round(openMs);
  const editor = page.getByTestId("editor").locator(".cm-content");

  // typing at the end
  await editor.click();
  await page.keyboard.press("Control+End");
  await typeAndMeasure("type at end", " The lamp burned low while the tide came in over the stones and nobody spoke.");
  // typing in the middle
  // (only lines near the viewport exist in the DOM: go up first, then into a paragraph a few screens down)
  await page.keyboard.press("Control+Home");
  for (let i = 0; i < 40; i++) await page.keyboard.press("ArrowDown");
  await page.keyboard.press("End");
  await typeAndMeasure("type in middle", " She waited by the door and listened to the wind.");

  // scrolling through, counting long tasks
  await page.evaluate(() => ((window as unknown as { __long: number[] }).__long = []));
  const [, scrollMs] = await timed(async () => {
    for (let i = 0; i < 30; i++) {
      await page.mouse.wheel(0, 1200);
      await page.waitForTimeout(30);
    }
  });
  const longs = await page.evaluate(() => (window as unknown as { __long: number[] }).__long);
  results["scroll 36k px ms"] = Math.round(scrollMs);
  results["scroll long tasks"] = longs.length;
  results["scroll longest task ms"] = longs.length ? Math.round(Math.max(...longs)) : 0;

  // the same at phone speed
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await editor.click();
  await page.keyboard.press("Control+End");
  await typeAndMeasure("phone: type at end", " The gulls were loud over the harbour that morning.");
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 30_000 });
});

// With PERF_SHOTS=<folder>: screenshots of the main pages with this much in the world, at desk and phone width.
test("screenshots", async () => {
  const dir = process.env.PERF_SHOTS;
  test.skip(!dir, "PERF_SHOTS not set");
  const shot = (name: string) => page.screenshot({ path: `${dir}/${name}.png` });
  for (const [w, h, tag] of [[1400, 900, "desk"], [390, 844, "phone"]] as const) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`${W}/bible`);
    await expect(page.getByTestId("bible-list").first()).toBeVisible();
    await shot(`${tag}-bible`);
    await page.goto(`${W}/bible/k/character`);
    await expect(page.getByTestId("bible-list")).toBeVisible();
    await shot(`${tag}-characters`);
    await page.getByTestId("bible-list").locator("tbody tr a").first().click();
    await expect(page.getByTestId("relationships")).toBeVisible();
    await shot(`${tag}-entry`);
    await page.goto(`${W}/bible/types`);
    await expect(page.getByTestId("relation-types").first()).toBeVisible();
    await shot(`${tag}-types`);
    await page.goto(`${W}/where`);
    await expect(page.getByTestId("where-grid")).toBeVisible();
    await shot(`${tag}-where`);
    await page.goto("/settings");
    await page.getByTestId("writing-settings").scrollIntoViewIfNeeded();
    await shot(`${tag}-settings`);
    await page.goto(`${W}/chapters/${results["chapter id"]}`);
    const name = page.getByTestId("editor").locator(".cm-name").first();
    await expect(name).toBeVisible();
    await shot(`${tag}-chapter`);
    await name.hover();
    await expect(page.getByTestId("name-card")).toBeVisible();
    await shot(`${tag}-card`);
    await page.mouse.move(0, 0);
    await page.getByTestId("editor").locator(".cm-line").first().click();
    await page.keyboard.press("Home");
    await page.keyboard.press("Control+Shift+ArrowRight");
    await expect(page.getByTestId("selection-strip").or(page.getByTestId("name-card"))).toBeVisible();
    await shot(`${tag}-selection`);
  }
});
