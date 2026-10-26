// Phase 15: pictures (docs/SPEC.md §17). The Pictures page in World settings, a gallery on an entry with its main
// picture on the page and on its card, a picture pasted into a chapter (drawn under its line, folded to a chip,
// Backspace and Undo), picture lines left out of the counts, one in an entry's notes, the full view, and pictures on
// the device offline. Every picture is drawn by the test (made-up shapes). Builds a world of its own.

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { STATE_FILE, waitForServiceWorker } from "./state";

test.describe.configure({ mode: "serial" });

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:8767";
const W = "/w/the-picture-coast";
const A = "/api/worlds/the-picture-coast";
let context: BrowserContext;
let page: Page;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
const ids: Record<string, string> = {};

async function api(method: string, path: string, data?: unknown): Promise<Json> {
  const r = await page.request.fetch(path, { method, data, headers: { Origin: BASE } });
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();
  return r.status() === 204 ? {} : r.json();
}

/** A made-up picture drawn in the browser: a coloured field with a block in one corner. */
async function drawn(width: number, height: number, colour: string): Promise<Buffer> {
  const b64 = await page.evaluate(
    async ([w, h, c]) => {
      const canvas = new OffscreenCanvas(w, h);
      const g = canvas.getContext("2d")!;
      g.fillStyle = c;
      g.fillRect(0, 0, w, h);
      g.fillStyle = "#222";
      g.fillRect(0, 0, w / 3, h / 4);
      const blob = await canvas.convertToBlob({ type: "image/png" });
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let s = "";
      for (const x of bytes) s += String.fromCharCode(x);
      return btoa(s);
    },
    [width, height, colour] as const,
  );
  return Buffer.from(b64, "base64");
}

async function upload(name: string, data: Buffer): Promise<Json> {
  const r = await page.request.post(`${A}/pictures`, { multipart: { file: { name, mimeType: "image/png", buffer: data } }, headers: { Origin: BASE } });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}

const editor = () => page.getByTestId("editor").locator(".cm-content");
const words = () => page.getByTestId("word-count");

test.beforeAll(async ({ browser }) => {
  context = await browser.newContext({ storageState: STATE_FILE });
  page = await context.newPage();
});

test.afterAll(async () => {
  await context.close();
});

test("the world for phase 15", async () => {
  await page.goto("/");
  await api("POST", "/api/worlds", { name: "The Picture Coast" });
  await api("POST", `${A}/projects`, { name: "The Salt Road" });
  ids.greywick = (await api("POST", `${A}/entities`, { name: "Greywick", kind: "place", summary: "A harbour town." })).id;
  ids.isolde = (await api("POST", `${A}/entities`, { name: "Isolde" })).id;
  for (let n = 1; n <= 8; n++) await api("POST", `${A}/projects/the-salt-road/chapters`, { title: `Chapter ${n}`, body: "Isolde waits.\n" });
  ids.c9 = (await api("POST", `${A}/projects/the-salt-road/chapters`, { title: "The Drowned Bell", body: "Isolde came down to Greywick.\n\nThe bell rang twice.\n" })).id;
});

test("17.1 the Pictures page: upload, used nowhere, rename, delete", async () => {
  await page.goto(`${W}/settings`);
  const section = page.getByTestId("pictures-page");
  await expect(section.getByTestId("pictures-total")).toHaveText("0 pictures · 0 kB");
  await section.getByTestId("pictures-file").setInputFiles({ name: "harbour-at-dusk.png", mimeType: "image/png", buffer: await drawn(800, 500, "#5b8aa6") });
  const row = section.getByTestId("picture-row");
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId("picture-name")).toHaveText("harbour-at-dusk");
  await expect(row.getByTestId("picture-uses")).toHaveText("Used nowhere");
  await row.getByTestId("picture-rename").click();
  await row.getByRole("textbox", { name: "Name" }).fill("harbour at dusk");
  await row.getByRole("button", { name: "Save" }).click();
  await expect(row.getByTestId("picture-name")).toHaveText("harbour at dusk");
  await expect(page.getByTestId("toast")).toContainText("Renamed to harbour at dusk");
  page.once("dialog", (d) => void d.accept());
  await row.getByTestId("picture-delete").click();
  await expect(section.getByTestId("picture-row")).toHaveCount(0);
});

test("17.2 a gallery on Greywick: main picture, caption, full view, Make main, Remove, From the world", async () => {
  ids.gate = (await upload("the-gate.png", await drawn(600, 800, "#8a6a4a"))).id;
  ids.plan = (await upload("the-plan.png", await drawn(900, 600, "#4a8a5a"))).id;
  await page.goto(`${W}/bible/${ids.greywick}`);
  const gallery = page.getByTestId("gallery");
  await expect(gallery).toContainText("Pictures · Add…");
  await expect(page.getByTestId("main-picture")).toHaveCount(0);
  await gallery.getByTestId("gallery-from-world").click();
  await page.getByTestId("picture-picker").getByRole("searchbox").fill("gate");
  await page.getByTestId("picker-thumb").first().click();
  await gallery.getByTestId("gallery-from-world").click();
  await page.locator(`[data-testid=picker-thumb][data-picture="${ids.plan}"]`).click();
  await expect(gallery.getByTestId("gallery-item")).toHaveCount(2);
  await expect(page.getByTestId("main-picture")).toHaveAttribute("data-picture", ids.gate);

  // a caption on the plan, then Make main
  const plan = gallery.locator(`[data-testid=gallery-item][data-picture="${ids.plan}"]`);
  await plan.getByTestId("gallery-more").click();
  await plan.getByTestId("caption").click();
  await plan.getByRole("textbox", { name: "Caption" }).fill("The harbour from above");
  await plan.getByRole("button", { name: "Save" }).click();
  await expect(plan.getByTestId("gallery-caption")).toHaveText("The harbour from above");
  await plan.getByTestId("gallery-more").click();
  await plan.getByTestId("make-main").click();
  await expect(page.getByTestId("main-picture")).toHaveAttribute("data-picture", ids.plan);
  await expect(page.getByTestId("main-caption")).toHaveText("The harbour from above");

  // the full view steps through both with the arrow keys; Esc closes it
  await page.getByTestId("main-picture").locator("button").click();
  const viewer = page.getByTestId("picture-viewer");
  await expect(viewer.getByTestId("viewer-img")).toHaveAttribute("data-picture", ids.plan);
  await page.keyboard.press("ArrowRight");
  await expect(viewer.getByTestId("viewer-img")).toHaveAttribute("data-picture", ids.gate);
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);

  // the card when resting on Greywick's name in chapter 9 shows the main picture
  await page.goto(`${W}/chapters/${ids.c9}`);
  await page.getByTestId("editor").locator(".cm-name", { hasText: "Greywick" }).hover();
  await expect(page.getByTestId("name-card").getByTestId("card-picture")).toHaveAttribute("src", `/api/pictures/${ids.plan}/thumb`);

  // Remove from this entry leaves the picture in the world, used nowhere
  await page.goto(`${W}/bible/${ids.greywick}`);
  const gate = page.getByTestId("gallery").locator(`[data-testid=gallery-item][data-picture="${ids.gate}"]`);
  await gate.getByTestId("gallery-more").click();
  await gate.getByTestId("remove-picture").click();
  await expect(page.getByTestId("gallery").getByTestId("gallery-item")).toHaveCount(1);
  await page.goto(`${W}/settings`);
  await expect(page.locator(`[data-testid=picture-row][data-picture="${ids.gate}"]`).getByTestId("picture-uses")).toHaveText("Used nowhere");
  await expect(page.locator(`[data-testid=picture-row][data-picture="${ids.plan}"]`).getByTestId("picture-uses")).toContainText("Greywick");
  await expect(page.locator(`[data-testid=picture-row][data-picture="${ids.plan}"]`).getByTestId("picture-delete")).toHaveCount(0);
});

test("17.3 a picture pasted into chapter 9: its line, the chip, Backspace and Undo, the counts", async () => {
  await page.goto(`${W}/chapters/${ids.c9}`);
  await expect(words()).toHaveText("9 words");
  await page.getByTestId("editor").locator(".cm-line", { hasText: "Isolde came down" }).click();
  await page.keyboard.press("End");
  const png = (await drawn(640, 400, "#a65b5b")).toString("base64");
  await page.evaluate((b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bytes], "bell.png", { type: "image/png" }));
    document.querySelector("[data-testid=editor] .cm-content")!.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  }, png);
  // the line goes in after the paragraph, with the cursor between the brackets
  const picLine = page.getByTestId("editor").locator(".cm-picture-line");
  await expect(picLine).toHaveCount(1);
  await page.keyboard.type("The bell at dusk");
  const block = page.getByTestId("editor").getByTestId("picture-block");
  await expect(block).toBeVisible();
  await expect(block.locator("img")).toBeVisible();
  await expect(block.locator("figcaption")).toHaveText("The bell at dusk");
  await expect(picLine).toContainText("(picture:");
  // the cursor leaves: the link folds into a chip; the word count is what it was, whatever the caption says
  await page.getByTestId("editor").locator(".cm-line", { hasText: "The bell rang" }).click();
  await expect(picLine.locator(".cm-picture-chip")).toBeVisible();
  await expect(picLine).not.toContainText("(picture:");
  await expect(words()).toHaveText("9 words");
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 15_000 });

  // Backspace just after the link deletes all of it; Undo brings it back
  await picLine.click();
  await page.keyboard.press("End");
  await page.keyboard.press("Backspace");
  await expect(page.getByTestId("editor").locator(".cm-picture-line")).toHaveCount(0);
  await expect(page.getByTestId("editor").locator(".cm-line", { hasText: "![The bell at dusk]" })).toBeVisible();
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("editor").locator(".cm-picture-line")).toHaveCount(1);

  // the server agrees: same words, Isolde mentioned once, the compiled manuscript without it
  await expect(page.getByTestId("save-status")).toHaveText("Saved", { timeout: 15_000 });
  const ch = await api("GET", `${A}/chapters/${ids.c9}`);
  expect(ch.words).toBe(9);
  expect(ch.mentions.filter((m: Json) => m.entity_name === "Isolde")).toHaveLength(1);
  ids.bell = /picture:([0-9a-f-]{36})/.exec(ch.body)![1]!;
  await page.goto(`${W}/settings`);
  await expect(page.locator(`[data-testid=picture-row][data-picture="${ids.bell}"]`).getByTestId("picture-uses")).toContainText("The Drowned Bell");
});

test("17.3 an image link inside a sentence stays text; a picture line in Greywick's notes shows on its page", async () => {
  const inline = await api("POST", `${A}/projects/the-salt-road/chapters`, { title: "Inline", body: `Isolde ![x](picture:${ids.gate}) waits.\n` });
  await page.goto(`${W}/chapters/${inline.id}`);
  await expect(editor()).toContainText(`picture:${ids.gate}`);
  await expect(page.getByTestId("editor").getByTestId("picture-block")).toHaveCount(0);

  const g = (await api("GET", `${A}/entities/${ids.greywick}`)).entity;
  await api("PATCH", `${A}/entities/${ids.greywick}`, { base_version: g.version, body: `A harbour town.\n\n![The gate at noon](picture:${ids.gate})\n\nIts bell is old.` });
  await page.goto(`${W}/bible/${ids.greywick}`);
  const notes = page.getByTestId("entry-notes");
  await expect(notes.getByTestId("picture-block").locator("img")).toBeVisible();
  await expect(notes.getByTestId("picture-block").locator("figcaption")).toHaveText("The gate at noon");
  await expect(notes).toContainText("Its bell is old.");
  await expect(notes).not.toContainText("picture:");
});

test("17.5 offline: chapter 9's picture is on the device; a picture never fetched shows its box; Upload… needs the network", async () => {
  await page.goto("/settings");
  await waitForServiceWorker(page);
  await page.goto("/settings");
  const offline = page.getByTestId("offline-settings");
  await offline.getByRole("button", { name: "Sync now" }).click();
  await expect(offline).toContainText("Synced.");
  await expect(offline.getByTestId("offline-pictures")).toHaveText(/Pictures: [1-9]\d* · \d+ kB/);

  // a chapter whose picture was never shown on this device
  const never = (await upload("never-seen.png", await drawn(300, 600, "#777"))).id;
  const other = await api("POST", `${A}/projects/the-salt-road/chapters`, { title: "Unseen", body: `![Not fetched](picture:${never})\n\nText.\n` });
  await page.goto(`${W}/chapters/${other.id}`);
  await expect(page.getByTestId("editor").getByTestId("picture-block")).toBeVisible();
  await page.goto(`${W}/chapters/${ids.c9}`);
  await expect(page.getByTestId("editor").getByTestId("picture-block").locator("img")).toBeVisible();

  await context.setOffline(true);
  try {
    await page.reload();
    const block = page.getByTestId("editor").getByTestId("picture-block");
    await expect(block.locator("img")).toBeVisible();
    await expect.poll(() => block.locator("img").evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    await page.goto(`${W}/settings`);
    await page.getByTestId("pictures-upload").click();
    await expect(page.getByTestId("pictures-error")).toHaveText("Pictures need the network");
  } finally {
    await context.setOffline(false);
  }
  void never;
});
