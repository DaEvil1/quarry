// How wide a label is drawn, for placing labels on the Timeline, the Chart and the Graph so they don't cross each
// other or a shape's outline. Measured once per font and text on a canvas and remembered; without a canvas (tests)
// it is estimated from the length.

let ctx: CanvasRenderingContext2D | null | undefined;
const cache = new Map<string, number>();

/** The width in pixels of `text` drawn in `font` (a CSS font shorthand, e.g. "600 11.5px system-ui"). */
export function textWidth(text: string, font: string): number {
  const key = `${font}\u0000${text}`;
  const known = cache.get(key);
  if (known !== undefined) return known;
  if (ctx === undefined) {
    try {
      ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
    } catch {
      ctx = null;
    }
  }
  let w: number;
  if (ctx) {
    ctx.font = font;
    w = ctx.measureText(text).width;
  } else {
    const px = Number(/([\d.]+)px/.exec(font)?.[1] ?? 12);
    w = text.length * px * 0.56;
  }
  if (cache.size > 5000) cache.clear();
  cache.set(key, w);
  return w;
}

/** The longest start of `text` (with "…") that fits in `room` pixels, or "" when not even three letters do. */
export function fitText(text: string, room: number, font: string): string {
  if (textWidth(text, font) <= room) return text;
  let lo = 0;
  let hi = text.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (textWidth(`${text.slice(0, mid).trimEnd()}…`, font) <= room) lo = mid;
    else hi = mid - 1;
  }
  return lo >= 3 ? `${text.slice(0, lo).trimEnd()}…` : "";
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const overlaps = (a: Box, b: Box, gap = 0) => a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;

/** Whether a box and a circle overlap. */
export function boxHitsCircle(b: Box, cx: number, cy: number, r: number): boolean {
  const nx = Math.max(b.x, Math.min(cx, b.x + b.w));
  const ny = Math.max(b.y, Math.min(cy, b.y + b.h));
  return (nx - cx) ** 2 + (ny - cy) ** 2 < r * r;
}

/** Whether a box and a line segment cross. */
export function boxHitsSegment(b: Box, x1: number, y1: number, x2: number, y2: number): boolean {
  // Liang–Barsky clipping: the segment touches the box if some part of it survives
  let t0 = 0;
  let t1 = 1;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const edges: [number, number][] = [[-dx, x1 - b.x], [dx, b.x + b.w - x1], [-dy, y1 - b.y], [dy, b.y + b.h - y1]];
  for (const [p, q] of edges) {
    if (p === 0) {
      if (q < 0) return false;
    } else {
      const r = q / p;
      if (p < 0) {
        if (r > t1) return false;
        if (r > t0) t0 = r;
      } else {
        if (r < t0) return false;
        if (r < t1) t1 = r;
      }
    }
  }
  return true;
}
