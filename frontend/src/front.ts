// A world's front page (docs/SPEC.md §14.4): what the server sends, and "Lately" worked out here, grouped by day in
// this device's time zone: the last ten days on which anything happened, however long ago, each saying how long ago
// it was, so a long gap is plain without being judged.

import { get } from "./api";

export interface FrontNote {
  source: "chapter" | "journal";
  id: string;
  title: string | null;
  project: string | null;
  /** a chapter's place in its book, a journal entry's date */
  position?: number | null;
  date?: string;
  note: string;
  cursor: number;
  updated_at: string | null;
}

export type LatelyEvent =
  | { kind: "words"; at: string; project: string | null; n: number }
  | { kind: "journal"; at: string; id: string }
  | { kind: "entity"; at: string; id: string; name: string; entity_kind: string; added: boolean }
  | { kind: "fact" | "relationship"; at: string }
  | { kind: "captured" | "closed"; at: string; item_kind: string }
  | { kind: "decision"; day: string };

export interface Front {
  premise: string | null;
  notes: FrontNote[];
  lately: LatelyEvent[];
  decisions: { id: string; decided_on: string; text: string; project: string | null }[];
  questions: { latest: { id: string; title: string | null; body: string; created_at: string; project: string | null }[]; count: number; oldest: string | null };
  projects: { slug: string; words: number; chapters: number; last_written: string | null }[];
}

export const getFront = (world: string) => get<Front>(`/api/worlds/${encodeURIComponent(world)}/front`);

/** A day as this device reads it: yyyy-mm-dd in its own time zone. */
export function localDay(iso: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export interface Day {
  day: string;
  words: { project: string | null; n: number }[];
  journal: number;
  entities: { id: string; name: string; kind: string; added: boolean }[];
  facts: number;
  relationships: number;
  captured: number;
  closed: number;
  decisions: number;
}

/** The last `days` days on which anything happened, newest first. */
export function lately(events: LatelyEvent[], days = 10): Day[] {
  const by = new Map<string, Day>();
  const dayOf = (e: LatelyEvent) => localDay(e.kind === "decision" ? e.day : e.at);
  const journal = new Map<string, Set<string>>();
  for (const e of events) {
    const d = dayOf(e);
    let x = by.get(d);
    if (!x) {
      x = { day: d, words: [], journal: 0, entities: [], facts: 0, relationships: 0, captured: 0, closed: 0, decisions: 0 };
      by.set(d, x);
    }
    switch (e.kind) {
      case "words": {
        const w = x.words.find((y) => y.project === e.project);
        if (w) w.n += e.n;
        else x.words.push({ project: e.project, n: e.n });
        break;
      }
      case "journal": {
        const seen = journal.get(d) ?? new Set<string>();
        seen.add(e.id);
        journal.set(d, seen);
        x.journal = seen.size;
        break;
      }
      case "entity":
        if (!x.entities.some((y) => y.id === e.id)) x.entities.push({ id: e.id, name: e.name, kind: e.entity_kind, added: e.added });
        break;
      case "fact":
        x.facts++;
        break;
      case "relationship":
        x.relationships++;
        break;
      case "captured":
        x.captured++;
        break;
      case "closed":
        x.closed++;
        break;
      case "decision":
        x.decisions++;
        break;
    }
  }
  return [...by.values()].sort((a, b) => b.day.localeCompare(a.day)).slice(0, days);
}

const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const say = (n: number) => (n <= 10 ? WORDS[n]! : String(n));

/** "today", "yesterday", "four days ago", "three weeks ago", "two months ago", "three years ago" */
export function howLongAgo(day: string, today = localDay(new Date().toISOString())): string {
  const ms = (s: string) => new Date(`${s}T12:00:00`).getTime();
  const days = Math.round((ms(today) - ms(day)) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${say(days)} days ago`;
  if (days < 60) return `${say(Math.floor(days / 7))} weeks ago`;
  if (days < 365) return `${say(Math.floor(days / 30))} months ago`;
  const years = Math.floor(days / 365.25);
  return years <= 1 ? "a year ago" : `${say(years)} years ago`;
}
