// History and the Timeline on the server (docs/SPEC.md §13.2): recording an event from a passage (with its Undo),
// tellings, and the chronology the Timeline reads besides the cards, the timeline and the graph.

import { del, get, post } from "./api";
import type { EntityRef } from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export interface Recorded {
  event: EntityRef;
  event_id: string;
  created: boolean;
  telling_id: string;
  relationships: string[];
  when_before: Record<string, unknown> | null;
  when: Record<string, unknown> | null;
  time_differs: boolean;
}

export const recordEvent = (
  world: string,
  body: {
    event_id?: string;
    name?: string;
    /** from a chapter, or from a journal entry (then the passage is a note, docs/SPEC.md §14.1.2) */
    chapter_id?: string;
    journal_id?: string;
    passage: string;
    taking: { entity_id: string; role: "involved" | "place" }[];
    when?: { time_at: number; time_approx: boolean } | null;
    time_choice?: "keep" | "use";
  },
) => post<Recorded>(`${base(world)}/events/record`, body);
export const undoRecord = (world: string, done: Recorded) => post(`${base(world)}/events/record/undo`, done);
export const deleteTelling = (world: string, id: string) => del(`${base(world)}/tellings/${id}`);

export interface Chronology {
  presence: { entity_id: string; place_id: string; chapter_id: string }[];
  tellings: { id: string; event_id: string; chapter_id: string | null; passage: string }[];
  /** how often each event is noted in the Journal (notes are never tellings) */
  notes?: Record<string, number>;
}
export const chronology = (world: string) => get<Chronology>(`${base(world)}/chronology`);

/** An event's telling, as its page shows it (Told in). */
export interface Telling {
  id: string;
  passage: string;
  chapter: { id: string; title: string; state: string } | null;
  /** where the passage is in its chapter (-1 when it can't be found) */
  at: number;
  /** the passage was edited so that it can't be found */
  changed: boolean;
}
