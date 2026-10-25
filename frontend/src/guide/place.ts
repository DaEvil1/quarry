// Where the Guide's caption goes (docs/SPEC.md §15.1): next to what the step points at, below it if it fits, else
// above, right or left, shifted to stay on screen; never over the target or over what the next step uses, and over as
// little text as can be helped. When nothing beside the target will do, the caption keeps to a corner. Pure, so it can
// be tested without a page: the overlay measures, this decides.

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}
export type Side = "below" | "above" | "right" | "left";
export interface Placement {
  left: number;
  top: number;
  side: Side | "corner";
}
interface Size {
  width: number;
  height: number;
}

const SIDES: Side[] = ["below", "above", "right", "left"];

export const right = (b: Box) => b.left + b.width;
export const bottom = (b: Box) => b.top + b.height;
/** `v` kept between `lo` and `hi`; `lo` when there is no room at all */
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** The area two boxes share (0 when they only touch). */
export function overlap(a: Box, b: Box): number {
  const w = Math.min(right(a), right(b)) - Math.max(a.left, b.left);
  const h = Math.min(bottom(a), bottom(b)) - Math.max(a.top, b.top);
  return w > 0 && h > 0 ? w * h : 0;
}

/** How far apart two boxes are at their nearest (0 when they touch or overlap). */
export function distance(a: Box, b: Box): number {
  const dx = Math.max(0, a.left - right(b), b.left - right(a));
  const dy = Math.max(0, a.top - bottom(b), b.top - bottom(a));
  return Math.hypot(dx, dy);
}

export interface PlaceInput {
  target: Box;
  card: Size;
  view: Size;
  /** what must stay uncovered besides the target: the element the next step uses */
  avoid?: Box[];
  /** whether there is text at a point of the page, sampled over each place tried, to cover as little as can be */
  isText?: (x: number, y: number) => boolean;
  gap?: number;
  margin?: number;
}

function candidate(side: Side, t: Box, card: Size, view: Size, gap: number, m: number): Box {
  const { width: w, height: h } = card;
  const x = (v: number) => clamp(v, m, view.width - m - w);
  const y = (v: number) => clamp(v, m, view.height - m - h);
  const cx = t.left + t.width / 2;
  const cy = t.top + t.height / 2;
  if (side === "below") return { left: x(cx - w / 2), top: bottom(t) + gap, width: w, height: h };
  if (side === "above") return { left: x(cx - w / 2), top: t.top - gap - h, width: w, height: h };
  if (side === "right") return { left: right(t) + gap, top: y(cy - h / 2), width: w, height: h };
  return { left: t.left - gap - w, top: y(cy - h / 2), width: w, height: h };
}

const onScreen = (b: Box, view: Size, m: number) =>
  b.left >= m - 0.5 && b.top >= m - 0.5 && right(b) <= view.width - m + 0.5 && bottom(b) <= view.height - m + 0.5;

/** How much text a place would cover: the share of a 4×3 grid of points over it that land on text. */
export function textCover(b: Box, isText?: (x: number, y: number) => boolean): number {
  if (!isText) return 0;
  let n = 0;
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 3; j++) if (isText(b.left + ((i + 0.5) * b.width) / 4, b.top + ((j + 0.5) * b.height) / 3)) n++;
  }
  return n / 12;
}

/** The corner a caption keeps to when nothing beside the target will do: bottom right, else the first clear one. */
export function corner(input: PlaceInput): Placement {
  const { card, view, target } = input;
  const m = input.margin ?? 16;
  const boxes = [view.height - m - card.height, m].flatMap((top) =>
    [view.width - m - card.width, m].map((left) => ({ left, top, width: card.width, height: card.height })),
  );
  const clear = boxes.find((b) => !overlap(b, target) && !(input.avoid ?? []).some((a) => overlap(b, a))) ?? boxes[0]!;
  return { left: clear.left, top: clear.top, side: "corner" };
}

export function placeCaption(input: PlaceInput): Placement {
  const { target, card, view } = input;
  const gap = input.gap ?? 12;
  const m = input.margin ?? 16;
  const avoid = input.avoid ?? [];
  let best: { box: Box; side: Side; cover: number } | null = null;
  for (const side of SIDES) {
    const box = candidate(side, target, card, view, gap, m);
    if (!onScreen(box, view, m) || overlap(box, target) || avoid.some((a) => overlap(box, a))) continue;
    // the first side, in order, that covers no text; else the one covering least, the earlier side on a tie
    const cover = textCover(box, input.isText);
    if (cover === 0) return { left: box.left, top: box.top, side };
    if (!best || cover < best.cover) best = { box, side, cover };
  }
  return best ? { left: best.box.left, top: best.box.top, side: best.side } : corner(input);
}

/**
 * The line from the caption to what it points at, between their nearest points, or null when they are close enough
 * (`near` px) to read as one.
 */
export function connector(card: Box, target: Box, near = 28): { x1: number; y1: number; x2: number; y2: number } | null {
  if (distance(card, target) <= near) return null;
  const on = (b: Box, p: { x: number; y: number }) => ({
    x: clamp(p.x, b.left, right(b)),
    y: clamp(p.y, b.top, bottom(b)),
  });
  const from = on(card, { x: target.left + target.width / 2, y: target.top + target.height / 2 });
  const to = on(target, from);
  return { x1: from.x, y1: from.y, x2: to.x, y2: to.y };
}

/**
 * Whether a target sits comfortably in view, so it needn't be scrolled: inside the view across, and between 12% and
 * 72% of its height down (where a caption below or above still fits); a tall one only needs its top in that band.
 */
export function comfortable(r: Box, view: Size): boolean {
  const lo = view.height * 0.12;
  const hi = view.height * 0.72;
  const vertical = r.height > hi - lo ? r.top >= 0 && r.top <= hi : r.top >= lo && bottom(r) <= hi;
  return vertical && r.left >= 0 && right(r) <= view.width;
}
