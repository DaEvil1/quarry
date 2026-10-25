// Reading an entry's thread through the planning (docs/SPEC.md §14.2): the journal entries, items and decisions that
// name it (or are tagged with it), oldest first, with a heading for each year and a quiet "· 3 years ·" between two
// sources more than a year apart. The journal part is worked out on the device from the offline copy and the matcher
// that colours names, like the book's reading; items and decisions come from the server (which reads the stored
// mentions and tags). The book and the planning are never mixed into one reading.

import type { PlanningDecision, PlanningItem } from "../journal";
import type { Matcher } from "./matcher";
import { paragraphs, type Gap, type Para } from "./thread";

export type PlanningKind = "journal" | "item" | "decision";

export interface PlanningEntry {
  id: string;
  entry_date: string;
  title: string | null;
  body: string;
  project: string | null;
}

export interface JournalBlock {
  kind: "journal";
  date: string;
  entry: PlanningEntry;
  /** paragraphs that name it, with gaps between (or every paragraph, reading whole entries) */
  blocks: (Para | Gap)[];
  count: number;
}
export interface ItemBlock {
  kind: "item";
  date: string;
  item: PlanningItem;
  /** tagged with it but not naming it */
  tagged: boolean;
}
export interface DecisionBlock {
  kind: "decision";
  date: string;
  decision: PlanningDecision;
  tagged: boolean;
}
export type Source = JournalBlock | ItemBlock | DecisionBlock;
export type Line = Source | { kind: "year"; year: number } | { kind: "gap-years"; years: number };

export interface PlanningInput {
  entries: PlanningEntry[];
  items: PlanningItem[];
  decisions: PlanningDecision[];
  matcher: Matcher;
  /** the entry, and the one read with it ("With…") */
  ids: string[];
  mode: "paragraphs" | "entries";
  kinds: Set<PlanningKind>;
  /** a project's slug: that project and the world's own planning; empty for the whole world */
  project?: string;
  /** only what is dated on or after this day ("Read them" from a journal entry, docs/SPEC.md §14.5) */
  from?: string;
}

const ORDER: Record<PlanningKind, number> = { journal: 0, item: 1, decision: 2 };
const DAY = 86_400_000;
const time = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00Z`).getTime();

/** A paragraph names every one of the ids. */
const namesAll = (p: Para, ids: string[]) => ids.every((id) => p.hits.some((h) => h.entityId === id));

export function planningReading(input: PlanningInput): { lines: Line[]; counts: { paragraphs: number; entries: number; items: number; decisions: number; from: number | null; to: number | null } } {
  const { ids, project } = input;
  const inProject = (p: string | null) => !project || p === null || p === project;
  const sources: Source[] = [];
  if (input.kinds.has("journal")) {
    for (const e of input.entries) {
      if (!inProject(e.project)) continue;
      const all = paragraphs(e.body, input.matcher).map((p) => ({ ...p, margin: false }));
      const hits = all.map((p) => namesAll(p, ids));
      const count = hits.filter(Boolean).length;
      if (input.mode === "entries") {
        const named = all.flatMap((p) => p.hits);
        if (!ids.every((id) => named.some((h) => h.entityId === id))) continue;
        sources.push({ kind: "journal", date: e.entry_date, entry: e, blocks: all.map((p, i) => ({ ...p, hit: hits[i]! })), count });
        continue;
      }
      if (!count) continue;
      const blocks: (Para | Gap)[] = [];
      let last = -1;
      hits.forEach((h, i) => {
        if (!h) return;
        if (last >= 0 && i > last + 1) blocks.push({ kind: "gap", paras: all.slice(last + 1, i) });
        blocks.push({ ...all[i]!, hit: true });
        last = i;
      });
      sources.push({ kind: "journal", date: e.entry_date, entry: e, blocks, count });
    }
  }
  const about = (x: { names: string[]; tagged: string[] }) => ids.every((id) => x.names.includes(id) || x.tagged.includes(id));
  const taggedOnly = (x: { names: string[]; tagged: string[] }) => ids.some((id) => !x.names.includes(id) && x.tagged.includes(id));
  if (input.kinds.has("item")) {
    for (const i of input.items) if (inProject(i.project) && about(i)) sources.push({ kind: "item", date: i.created_at.slice(0, 10), item: i, tagged: taggedOnly(i) });
  }
  if (input.kinds.has("decision")) {
    for (const d of input.decisions) if (inProject(d.project) && about(d)) sources.push({ kind: "decision", date: d.decided_on, decision: d, tagged: taggedOnly(d) });
  }
  if (input.from) for (let i = sources.length - 1; i >= 0; i--) if (sources[i]!.date < input.from) sources.splice(i, 1);
  // oldest first; on the same day journal entries, then items, then decisions
  sources.sort((a, b) => a.date.localeCompare(b.date) || ORDER[a.kind] - ORDER[b.kind]);
  const lines: Line[] = [];
  let year: number | null = null;
  let prev: string | null = null;
  for (const s of sources) {
    if (prev !== null && time(s.date) - time(prev) > 365 * DAY) {
      lines.push({ kind: "gap-years", years: Math.max(1, Math.floor((time(s.date) - time(prev)) / (365.25 * DAY))) });
    }
    const y = Number(s.date.slice(0, 4));
    if (y !== year) lines.push({ kind: "year", year: y });
    year = y;
    prev = s.date;
    lines.push(s);
  }
  const years = sources.map((s) => Number(s.date.slice(0, 4)));
  return {
    lines,
    counts: {
      paragraphs: sources.reduce((k, s) => k + (s.kind === "journal" ? s.count : 0), 0),
      entries: sources.filter((s) => s.kind === "journal").length,
      items: sources.filter((s) => s.kind === "item").length,
      decisions: sources.filter((s) => s.kind === "decision").length,
      from: years.length ? Math.min(...years) : null,
      to: years.length ? Math.max(...years) : null,
    },
  };
}

const n = (k: number, one: string, many: string) => `${k.toLocaleString()} ${k === 1 ? one : many}`;

/** "Varren in the planning: 48 paragraphs in 19 journal entries, 11 items, 6 decisions · 2014–2026" */
export function planningCount(names: string[], c: ReturnType<typeof planningReading>["counts"]): string {
  const parts = [
    `${n(c.paragraphs, "paragraph", "paragraphs")} in ${n(c.entries, "journal entry", "journal entries")}`,
    n(c.items, "item", "items"),
    n(c.decisions, "decision", "decisions"),
  ];
  const span = c.from === null ? "" : c.from === c.to ? ` · ${c.from}` : ` · ${c.from}–${c.to}`;
  return `${names.join(" and ")} in the planning: ${parts.join(", ")}${span}`;
}
