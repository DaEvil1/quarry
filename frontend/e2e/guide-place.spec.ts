// The Guide's caption beside what it points at (docs/SPEC.md §15.1): a target low on a long page is scrolled into
// view before it shows, and the caption sits next to it without covering it, at three desk widths; on a phone the
// caption stays docked at the bottom with a line up to the target. "Getting back in" points at the front page's open
// questions, low on a long page, at its sixth step.

import { expect, test, type Page } from "@playwright/test";

import { STATE_FILE } from "./state";

type R = { left: number; top: number; right: number; bottom: number; width: number; height: number };

const rect = (page: Page, sel: string) =>
  page.locator(sel).first().evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
  }) as Promise<R>;
const overlaps = (a: R, b: R) => Math.min(a.right, b.right) > Math.max(a.left, b.left) && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);
const gapBetween = (a: R, b: R) =>
  Math.hypot(Math.max(0, a.left - b.right, b.left - a.right), Math.max(0, a.top - b.bottom, b.top - a.bottom));

const SIZES = [
  { name: "1280", width: 1280, height: 800 },
  { name: "1920", width: 1920, height: 1080 },
  { name: "2560", width: 2560, height: 1440 },
  { name: "phone", width: 390, height: 844 },
];

for (const size of SIZES) {
  test(`at ${size.name}: a low target is scrolled into view and the caption sits by it`, async ({ browser }) => {
    const context = await browser.newContext({ storageState: STATE_FILE, viewport: { width: size.width, height: size.height } });
    await context.addInitScript(() => localStorage.setItem("quarry.guide.pace", JSON.stringify("instant")));
    const page = await context.newPage();
    await page.goto("/guide");
    await page.getByTestId("guide-tour-back-in").getByTestId("guide-try").click();
    const guide = page.getByTestId("guide");
    await expect(guide).toContainText("1 of", { timeout: 30_000 });

    // tried, each step waits for Next: on to the open questions
    await expect(async () => {
      if (await guide.locator(".guide-say").filter({ hasText: "Questions still open" }).count()) return;
      await guide.getByTestId("guide-next").click({ timeout: 1000 });
      await expect(guide.locator(".guide-say")).toContainText("Questions still open", { timeout: 800 });
    }).toPass({ timeout: 30_000 });

    const target = '[data-testid="open-questions"]';
    const card = '[data-testid="guide-card"]';
    // scrolled into view: wholly on screen, its top in the upper part of the window
    await expect.poll(async () => {
      const t = await rect(page, target);
      return t.top >= 0 && t.top <= size.height * 0.72 && t.bottom <= size.height;
    }).toBe(true);
    // the caption settles beside it (it slides there), never over it
    await expect.poll(async () => {
      const [t, c] = await Promise.all([rect(page, target), rect(page, card)]);
      if (overlaps(t, c)) return "overlaps";
      if (size.name !== "phone" && gapBetween(t, c) > 40) return `${Math.round(gapBetween(t, c))} px away`;
      return "ok";
    }, { timeout: 5000 }).toBe("ok");
    const side = await page.locator(card).getAttribute("data-side");
    if (size.name === "phone") {
      expect(side).toBe("docked");
      const c = await rect(page, card);
      expect(c.bottom).toBeGreaterThan(size.height * 0.75);
      await expect(page.getByTestId("guide-line")).toBeVisible();
    } else {
      expect(["below", "above", "right", "left"]).toContain(side);
    }
    await context.close();
  });
}
