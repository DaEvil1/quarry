// An entry's own timeline (docs/SPEC.md §13.2.5): its slice of the Timeline, in happened order, each row with its
// time: for a character their birth, the events they are related to, runs of "is at", relationships starting and
// ending (with roles), their death, and their age on each row; for a place, what happened there and who was there;
// for a faction, its events, members joining and leaving and who held each role; for an event, its time, its tellings
// and the ages of the people in it; for anything else, the events it is related to. Worked out when shown.

import type { Chronology } from "../history";
import type { StoryChapter } from "../types";
import type { Card } from "./cards";
import { ageText, birthOf, deathOf, eraAt, eventTime, type Era } from "./eras";
import { timeText, type Unit } from "./when";

export interface SliceRow {
  key: string;
  /** where it sits in time (null: not placed, listed last) */
  t: number | null;
  approx: boolean;
  /** its place in book order, to order rows at the same time */
  book: number;
  when: string;
  era: Era | null;
  text: string;
  /** the entry it is about, to link to */
  link?: { entity?: string; chapter?: string; at?: number };
  age?: string;
}

interface Input {
  card: Card;
  cards: Map<string, Card>;
  timeline: StoryChapter[];
  chronology: Chronology | null;
  eras: Era[];
  unit: Unit;
}

const EVENT_TYPES = (c: Card) => c.facts.filter((f) => f.label.trim().toLowerCase() === "type").map((f) => f.value.trim().toLowerCase());

export function entitySlice({ card, cards, timeline, chronology, eras, unit }: Input): SliceRow[] {
  const chapters = new Map(timeline.map((c) => [c.id, c]));
  const chapterTime = (id: string | null | undefined) => {
    const ch = id ? chapters.get(id) : undefined;
    return ch && !ch.early && ch.clock !== null && ch.set_time != null ? { t: ch.set_time, approx: !!ch.set_approx, book: ch.index } : null;
  };
  const rows: SliceRow[] = [];
  const at = (t: number | null, approx: boolean, book: number, text: string, key: string, link?: SliceRow["link"]) =>
    rows.push({ key, t, approx, book, when: t === null ? "" : timeText({ time_at: t, time_approx: approx }, unit), era: eraAt(t, eras), text, link });
  const spanStart = (x: { from: string | null; from_time?: number; from_approx?: boolean }) =>
    x.from_time != null ? { t: x.from_time, approx: !!x.from_approx, book: Infinity } : chapterTime(x.from);
  const spanEnd = (x: { until: string | null; until_time?: number; until_approx?: boolean }) =>
    x.until_time != null ? { t: x.until_time, approx: !!x.until_approx, book: Infinity } : chapterTime(x.until);
  const eventRow = (ev: Card, how: string) => {
    const t = eventTime(ev, chapters);
    at(t?.t ?? null, t?.approx ?? false, Infinity, how ? `${how} ${ev.name}` : ev.name, `ev:${ev.id}:${how}`, { entity: ev.id });
  };

  if (card.kind === "character") {
    const birth = birthOf(card, cards, chapters);
    const death = deathOf(card, cards, chapters);
    if (birth) at(birth.t, birth.approx, -1, "born", "born");
    for (const r of card.relations) {
      const other = cards.get(r.other.id);
      if (!other) continue;
      if (other.kind === "event") {
        const types = EVENT_TYPES(other);
        if (!types.includes("birth") && !types.includes("death")) eventRow(other, r.label);
        continue;
      }
      if (other.kind === "species") continue;
      const role = r.role ? ` · ${r.role}` : "";
      const s = spanStart(r);
      if (s) at(s.t, s.approx, s.book, `${r.label} ${r.other.name}${role}`, `rel:${r.other.id}:${r.label}:from:${s.t}`, { entity: r.other.id });
      const e = spanEnd(r);
      if (e) at(e.t, e.approx, e.book, `no longer ${r.label} ${r.other.name}${role}`, `rel:${r.other.id}:${r.label}:until:${e.t}`, { entity: r.other.id });
    }
    // runs of "is at": each run of chapters (in happened order) at the same place, one row
    const here = (chronology?.presence ?? [])
      .filter((p) => p.entity_id === card.id && chapters.get(p.chapter_id)?.clock != null)
      .sort((a, b) => chapters.get(a.chapter_id)!.clock! - chapters.get(b.chapter_id)!.clock!);
    let run: { place: string; first: StoryChapter; last: StoryChapter } | null = null;
    const flush = () => {
      if (!run) return;
      const p = cards.get(run.place);
      const nums = run.first === run.last ? `chapter ${run.first.index + 1}` : `chapters ${run.first.index + 1}–${run.last.index + 1}`;
      const t = chapterTime(run.first.id);
      at(t?.t ?? null, t?.approx ?? false, run.first.index, `at ${p?.name ?? "?"} · ${nums}`, `at:${run.place}:${run.first.id}`, { entity: run.place });
    };
    for (const p of here) {
      const ch = chapters.get(p.chapter_id)!;
      if (run && run.place === p.place_id) run.last = ch;
      else {
        flush();
        run = { place: p.place_id, first: ch, last: ch };
      }
    }
    flush();
    if (death) at(death.t, death.approx, Infinity, "died", "died");
    for (const r of rows) {
      if (r.t === null || r.key === "born") continue;
      const a = ageText(birth, death && r.key !== "died" ? death : null, { t: r.t, approx: r.approx });
      if (a && a !== "not born yet") r.age = r.key === "died" ? a.replace(/^age /, "at ") : a;
    }
  } else if (card.kind === "event") {
    const t = eventTime(card, chapters);
    if (t) at(t.t, t.approx, -1, t.end != null ? `${card.name}, to ${timeText({ time_at: t.end }, unit)}` : card.name, "self");
    for (const tl of (chronology?.tellings ?? []).filter((x) => x.event_id === card.id)) {
      const ch = tl.chapter_id ? chapters.get(tl.chapter_id) : undefined;
      const ct = chapterTime(tl.chapter_id);
      rows.push({ key: `told:${tl.id}`, t: null, approx: false, book: ch?.index ?? Infinity, when: ct ? timeText({ time_at: ct.t, time_approx: ct.approx }, unit) : "", era: eraAt(ct?.t, eras), text: `told in ${ch?.title ?? "a chapter not in the book"}`, link: ch ? { chapter: ch.id } : undefined });
    }
    // the ages of the people in it
    for (const r of card.relations) {
      const who = cards.get(r.other.id);
      if (!who || who.kind !== "character" || !t) continue;
      const a = ageText(birthOf(who, cards, chapters), deathOf(who, cards, chapters), { t: t.t, approx: t.approx });
      if (a) rows.push({ key: `age:${who.id}`, t: t.t, approx: t.approx, book: Infinity, when: "", era: null, text: `${who.name} ${r.label === "involved" ? "takes part" : r.label}`, link: { entity: who.id }, age: a });
    }
  } else {
    for (const r of card.relations) {
      const other = cards.get(r.other.id);
      if (other?.kind === "event") eventRow(other, card.kind === "place" ? "" : r.label);
      else if (card.kind === "faction" && other?.kind === "character") {
        const role = r.role ? ` · ${r.role}` : "";
        const s = spanStart(r);
        if (s) at(s.t, s.approx, s.book, `${other.name} joins${role}`, `join:${other.id}:${s.t}`, { entity: other.id });
        const e = spanEnd(r);
        if (e) at(e.t, e.approx, e.book, `${other.name} leaves${role}`, `leave:${other.id}:${e.t}`, { entity: other.id });
      }
    }
    if (card.kind === "place") {
      // who was there when, from "is at"
      for (const p of (chronology?.presence ?? []).filter((x) => x.place_id === card.id)) {
        const ch = chapters.get(p.chapter_id);
        const who = cards.get(p.entity_id);
        if (!ch || !who) continue;
        const t = chapterTime(ch.id);
        at(t?.t ?? null, t?.approx ?? false, ch.index, `${who.name} here · chapter ${ch.index + 1}`, `here:${who.id}:${ch.id}`, { entity: who.id });
      }
    }
  }
  return rows.sort((a, b) => (a.t ?? Infinity) - (b.t ?? Infinity) || a.book - b.book || a.text.localeCompare(b.text));
}
