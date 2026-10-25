import { describe, expect, it } from "vitest";

import { bottom, comfortable, connector, distance, overlap, placeCaption, right, type Box } from "./guide/place";

// a 1280×800 window and a 360×140 caption, as at the desk
const view = { width: 1280, height: 800 };
const card = { width: 360, height: 140 };
const box = (left: number, top: number, width: number, height: number): Box => ({ left, top, width, height });
const at = (p: { left: number; top: number }): Box => box(p.left, p.top, card.width, card.height);
const onScreen = (b: Box) => b.left >= 16 && b.top >= 16 && right(b) <= view.width - 16 && bottom(b) <= view.height - 16;

describe("placing the Guide's caption (docs/SPEC.md §15.1)", () => {
  it("goes below its target, centred under it, when there is room", () => {
    const target = box(500, 200, 200, 40);
    const p = placeCaption({ target, card, view });
    expect(p.side).toBe("below");
    expect(p.top).toBe(bottom(target) + 12);
    expect(p.left + card.width / 2).toBe(600);
    expect(overlap(at(p), target)).toBe(0);
  });

  it("goes above when there is no room below, and shifts sideways to stay on screen", () => {
    const target = box(1180, 690, 90, 40);
    const p = placeCaption({ target, card, view });
    expect(p.side).toBe("above");
    expect(onScreen(at(p))).toBe(true);
    expect(right(at(p))).toBe(view.width - 16);
    expect(distance(at(p), target)).toBe(12);
  });

  it("goes beside a tall target, right before left", () => {
    expect(placeCaption({ target: box(100, 20, 300, 760), card, view }).side).toBe("right");
    expect(placeCaption({ target: box(880, 20, 380, 760), card, view }).side).toBe("left");
  });

  it("keeps clear of what the next step uses", () => {
    const target = box(500, 200, 200, 40);
    const next = box(450, 260, 300, 60);
    const p = placeCaption({ target, card, view, avoid: [next] });
    expect(p.side).toBe("above");
    expect(overlap(at(p), next)).toBe(0);
  });

  it("would rather cover no text: past a side over text to one that is clear", () => {
    const target = box(500, 300, 200, 40);
    const textBelow = (_x: number, y: number) => y > 340;
    expect(placeCaption({ target, card, view, isText: textBelow }).side).toBe("above");
    // text everywhere: the first side in order still wins
    expect(placeCaption({ target, card, view, isText: () => true }).side).toBe("below");
  });

  it("keeps to a corner when nothing beside the target will do, one clear of the target if there is one", () => {
    const whole = box(0, 0, 1280, 800);
    expect(placeCaption({ target: whole, card, view })).toEqual({ left: 1280 - 16 - 360, top: 800 - 16 - 140, side: "corner" });
    // a wide band from just under the top to near the bottom: no side fits, the top right corner is clear
    const band = box(0, 160, 1280, 610);
    const p = placeCaption({ target: band, card, view });
    expect(p.side).toBe("corner");
    expect(overlap(at(p), band)).toBe(0);
  });
});

describe("the line from the caption to its target", () => {
  it("is drawn only when they are apart, from the caption's nearest edge to the target's", () => {
    const target = box(100, 100, 100, 40);
    expect(connector(box(100, 152, 360, 140), target)).toBeNull();
    const l = connector(box(900, 600, 360, 140), target)!;
    expect(l).toEqual({ x1: 900, y1: 600, x2: 200, y2: 140 });
  });
});

describe("whether a target needs scrolling into view", () => {
  it("is left alone in the middle band, scrolled when near an edge or off screen", () => {
    expect(comfortable(box(100, 300, 200, 40), view)).toBe(true);
    expect(comfortable(box(100, 700, 200, 40), view)).toBe(false);
    expect(comfortable(box(100, 40, 200, 40), view)).toBe(false);
    expect(comfortable(box(100, 1400, 200, 40), view)).toBe(false);
    // a tall one only needs its top in the band
    expect(comfortable(box(100, 200, 600, 1200), view)).toBe(true);
  });
});
