// Decisions with follow-ups (docs/SPEC.md §16): the planned facts and relationships and the tasks that carry a
// decision out, its state worked out from them, and the gap a written chapter shows. Everything here is read when
// asked (a decision's line, a chapter opened, Loose ends shown), never while typing.

import { ref } from "vue";

import { del, get, post } from "./api";
import type { EntityKind, EntityRef } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

/** The toast of a follow-up made, dropped or made canon ("Task added · follows the decision · Undo"): shown by the app
 * shell above any other toast, so it outlives the step that made it. */
export const followupToast = ref<{ label: string; undo: (() => Promise<void>) | null } | null>(null);

/** How many follow-ups are to do, done and dropped; null (or absent) for a settled decision. */
export interface FollowupCounts {
  todo: number;
  done: number;
  dropped: number;
}

export type FollowupState = "todo" | "done" | "dropped";

/** One line of a decision's follow-up list. */
export interface Followup {
  id: string;
  state: FollowupState;
  /** the row in words, kept for when it is gone */
  what: string;
  dropped_on: string | null;
  /** null once its row is gone */
  kind: "fact" | "relationship" | "task" | null;
  /** the row as it reads now ("Varren · status: dead · from chapter 9, The Drowned Bell"), or `what` */
  text: string;
  standing: "canon" | "planned" | "rumour" | null;
  status: string | null;
  closed_at: string | null;
  link: { entity?: string; fact?: string; relationship?: string; item?: string } | null;
  /** a current chapter with text this planned change is tied to (§16.4) */
  written: { id: string; title: string; n: number } | null;
}

/** A decision, as a follow-up's row shows it ("follows the decision of 12 Oct 2026"). */
export interface Follows {
  id: string;
  decided_on: string;
  text: string;
  followup_id?: string;
}

/** A decision's line wherever it is shown, with what the follow-up step needs. */
export interface DecisionLine {
  id: string;
  decided_on: string;
  text: string;
  project: string | null;
  followups?: FollowupCounts | null;
}

export interface NamedChapter {
  id: string;
  title: string;
  n: number;
  project: string;
  project_name: string;
  /** "chapter 9, The Drowned Bell" (with its project's name when a decision with no project could mean several) */
  label: string;
}

export interface Offers {
  chapters: NamedChapter[];
  /** tagged first (ticked in the task form), then named */
  entities: (EntityRef & { tagged: boolean })[];
}

export interface Candidate {
  table: "fact" | "relationship" | "item";
  id: string;
  text: string;
}

/** A gap line in a chapter's Loose ends (§16.4). */
export interface Gap {
  followup_id: string;
  /** the resolution key of Not yet */
  key: string;
  table: "fact" | "relationship";
  id: string;
  what: string;
  standing: string;
  version: number;
  decision: Follows;
  /** the decision's other follow-ups still to do */
  others_todo: number;
  /** the resolution id when put off with Not yet */
  not_yet: string | null;
  entity_id: string;
  label?: string;
  type_id?: string;
  a_id?: string;
  b_id?: string;
}

export interface Added {
  followup: Followup;
  made: { table: "fact" | "relationship" | "item"; id: string } | null;
  counts: FollowupCounts | null;
}

export const listFollowups = (world: string, decision: string) =>
  get<Followup[]>(`${base(world)}/decisions/${decision}/followups`);
export const addFollowup = (world: string, decision: string, body: Record<string, unknown>) =>
  post<Added>(`${base(world)}/decisions/${decision}/followups`, body);
export const dropFollowup = (world: string, decision: string, id: string) =>
  post<{ followup: Followup; counts: FollowupCounts | null }>(`${base(world)}/decisions/${decision}/followups/${id}/drop`);
export const undropFollowup = (world: string, decision: string, id: string) =>
  post<{ followup: Followup; counts: FollowupCounts | null }>(`${base(world)}/decisions/${decision}/followups/${id}/undrop`);
export const detachFollowup = (world: string, decision: string, id: string) =>
  del<{ attach: { table: string; id: string; any: boolean } | null; counts: FollowupCounts | null }>(
    `${base(world)}/decisions/${decision}/followups/${id}`,
  );
export const decisionOffers = (world: string, decision: string) => get<Offers>(`${base(world)}/decisions/${decision}/offers`);
export const candidates = (world: string, decision: string) =>
  get<Candidate[]>(`${base(world)}/followup-candidates?decision=${encodeURIComponent(decision)}`);
export const chapterGaps = (world: string, chapter: string) => get<Gap[]>(`${base(world)}/chapters/${chapter}/gaps`);
export const getDecision = (world: string, id: string) => get<DecisionLine & { entities: EntityRef[]; item_id: string | null }>(`${base(world)}/decisions/${id}`);

/** The pill: nothing for a settled decision, "1 of 2 to do", or "done" once none is to do (§16.2). */
export function pillText(c: FollowupCounts | null | undefined): string | null {
  if (!c) return null;
  const all = c.todo + c.done + c.dropped;
  if (!all) return null;
  return c.todo ? `${c.todo} of ${all} to do` : "done";
}

/** "12 Oct 2026" */
export function decisionDay(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${iso.slice(0, 10)}T12:00:00`));
}

/** "20 Oct": a done or dropped follow-up's day, in the list. */
export function shortDay(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(new Date(iso.length > 10 ? iso : `${iso}T12:00:00`));
}

/** The tail of a follow-up line: "planned", "task · accepted 20 Oct", "22 Oct · the row was deleted". */
export function followupTail(f: Followup): string {
  if (f.kind === "task") {
    const when = f.closed_at && f.state !== "todo" ? ` ${shortDay(f.closed_at)}` : "";
    return `task · ${f.status}${when}`;
  }
  if (f.kind) return f.state === "dropped" && f.dropped_on ? `${f.standing} · dropped ${shortDay(f.dropped_on)}` : (f.standing ?? "");
  return [f.dropped_on ? shortDay(f.dropped_on) : "", "the row was deleted"].filter(Boolean).join(" · ");
}

/** "1 planned fact and 1 task follow this decision." for its delete warning (§16.1). */
export function followersText(list: Followup[]): string {
  const live = list.filter((f) => f.kind);
  if (!live.length) return "";
  const n = (k: Followup["kind"], one: string, many: string) => {
    const c = live.filter((f) => f.kind === k).length;
    return c ? `${c} ${c === 1 ? one : many}` : "";
  };
  const parts = [n("fact", "planned fact", "planned facts"), n("relationship", "planned relationship", "planned relationships"), n("task", "task", "tasks")].filter(Boolean);
  const joined = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
  return `${joined} ${live.length === 1 ? "follows" : "follow"} this decision. They stay, without the decision.`.replace("They stay", live.length === 1 ? "It stays" : "They stay");
}

/** Order the decisions a row could follow: those tagged with its entries first, then the rest, newest first. */
export function followOrder<T extends { decided_on: string; created_at?: string; entities?: { id: string }[] }>(list: T[], entities: string[]): T[] {
  const mine = (d: T) => (d.entities ?? []).some((e) => entities.includes(e.id));
  const newest = (a: T, b: T) => b.decided_on.localeCompare(a.decided_on) || (b.created_at ?? "").localeCompare(a.created_at ?? "");
  return [...list.filter(mine).sort(newest), ...list.filter((d) => !mine(d)).sort(newest)];
}

export type { EntityKind };
