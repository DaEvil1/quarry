// A focus per world (docs/SPEC.md §14.9): Writing (the default) or Planning, kept on the server per person and world.
// It decides where the world opens, the order of the nav, and where "Include planned" on the checks starts. The last
// place used in each world is kept on this device, for opening it under Writing.

import { put } from "./api";
import type { RouteLocationRaw } from "vue-router";
import type { World } from "./types";

export type Focus = "writing" | "planning";

export const focusOf = (w: World | undefined): Focus => (w?.focus === "planning" ? "planning" : "writing");

export const setFocus = (world: string, focus: Focus) => put<World>(`/api/worlds/${encodeURIComponent(world)}/focus`, { focus });

const PLACE_KEY = "quarry.place";

/** Remember the last page used in a world (its path), for opening the world there under Writing. */
export function writeLastPlace(world: string, path: string): void {
  try {
    const all = JSON.parse(localStorage.getItem(PLACE_KEY) ?? "{}") as Record<string, string>;
    all[world] = path;
    localStorage.setItem(PLACE_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable */
  }
}

export function readLastPlace(world: string): string | null {
  try {
    const all = JSON.parse(localStorage.getItem(PLACE_KEY) ?? "{}") as Record<string, unknown>;
    const v = all[world];
    return typeof v === "string" && v.startsWith(`/w/${world}/`) ? v : null;
  } catch {
    return null;
  }
}

/** Where opening a world leads: under Planning its front page; under Writing the last place used in it on this
 * device, or its front page. */
export function worldTarget(w: World): RouteLocationRaw {
  if (focusOf(w) === "writing") {
    const last = readLastPlace(w.slug);
    if (last) return last;
  }
  return { name: "world", params: { world: w.slug } };
}

// ---- Include planned (docs/SPEC.md §14.6): starts from the focus; set by hand, it stays until the focus changes ----

const PLANNED_KEY = "quarry.planned";

export function includePlanned(w: World | undefined): boolean {
  if (!w) return false;
  try {
    const all = JSON.parse(localStorage.getItem(PLANNED_KEY) ?? "{}") as Record<string, { on: boolean; focus: Focus }>;
    const kept = all[w.slug];
    if (kept && kept.focus === focusOf(w)) return kept.on;
  } catch {
    /* nothing kept */
  }
  return focusOf(w) === "planning";
}

export function setIncludePlanned(w: World, on: boolean): void {
  try {
    const all = JSON.parse(localStorage.getItem(PLANNED_KEY) ?? "{}") as Record<string, { on: boolean; focus: Focus }>;
    all[w.slug] = { on, focus: focusOf(w) };
    localStorage.setItem(PLANNED_KEY, JSON.stringify(all));
  } catch {
    /* shown now, not kept */
  }
}
