// Item calls shared by the inbox, triage and project views.

import { ApiError, del, get, patch, post } from "./api";
import { localToday, type CloseStatus, type Item, type ItemKind } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export interface ItemQuery {
  status?: "open" | "deferred" | "closed" | "all";
  project?: string;
  kind?: ItemKind;
  order?: "newest" | "oldest";
  limit?: number;
}

export function listItems(world: string, q: ItemQuery = {}): Promise<Item[]> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v) params.set(k, String(v));
  const qs = params.toString();
  return get<Item[]>(`${base(world)}/items${qs ? `?${qs}` : ""}`);
}

export function closeItem(
  world: string,
  id: string,
  status: CloseStatus,
  opts: { decision?: string; note?: string } = {},
): Promise<{ item: Item; decision_id: string | null }> {
  return post(`${base(world)}/items/${id}/close`, { status, ...opts, decided_on: localToday() });
}

/** Remove a decision; `made`: the follow-ups whose rows were made in its follow-up step go too (docs/SPEC.md §16.1). */
export function deleteDecision(world: string, id: string, made: string[] = []): Promise<void> {
  const q = made.map((m) => `made=${encodeURIComponent(m)}`).join("&");
  return del(`${base(world)}/decisions/${id}${q ? `?${q}` : ""}`);
}

/** Undo a close: reopen the item and remove the decision that came with it, with the rows made in its follow-up step
 * (those attached stay, unlinked). */
export async function undoClose(world: string, id: string, decisionId: string | null, made: string[] = []): Promise<void> {
  await reopenItem(world, id);
  if (decisionId) await deleteDecision(world, decisionId, made);
}

export function reopenItem(world: string, id: string): Promise<Item> {
  return post(`${base(world)}/items/${id}/reopen`);
}

/** The item changed on another device since it was loaded here; `current` is the server's copy. */
export class ItemConflict extends Error {
  constructor(public current: Item) {
    super("This item changed on another device. Showing the newer version.");
  }
}

export async function updateItem(
  world: string,
  item: Item,
  changes: Partial<Pick<Item, "kind" | "title" | "body" | "project">>,
): Promise<Item> {
  try {
    return await patch<Item>(`${base(world)}/items/${item.id}`, { base_version: item.version, ...changes });
  } catch (e) {
    const current = e instanceof ApiError && e.status === 409 ? (e.body as { item?: Item } | null)?.item : null;
    if (current) throw new ItemConflict(current);
    throw e;
  }
}

/** "3 h ago", "yesterday", "12 Oct": how old a capture is, at a glance. */
export function age(iso: string, now = Date.now()): string {
  const then = new Date(iso).getTime();
  const min = Math.round((now - then) / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  if (d === 1) return "yesterday";
  if (d < 7) return `${d} days ago`;
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(new Date(iso));
}
