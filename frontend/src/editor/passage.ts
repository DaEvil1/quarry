// Recording from a selected passage (docs/SPEC.md §14.1.2, §14.3.1), the same in a chapter and a journal entry:
// "Record a fact" (with "Make it canon here" in a chapter, for what was planned before) and a spark, question or task
// made from the passage, linked back to it. The page gives where it is and what to do afterwards.

import { addFact, factSuggestions, getEntity, type KindSuggestions } from "../bible";
import { journalDay } from "../journal";
import { norm } from "../world/time";
import type { EntityKind, EntityRef } from "../types";
import type { PassageActions } from "./strips";

export interface PassageContext {
  world: string;
  where: "chapter" | "journal";
  /** the chapter's id, or the journal entry's */
  sourceId: string;
  /** the project an item made here belongs to (the chapter's, the journal entry's, or none) */
  project: string | null;
  /** every entry, for "Other…" */
  names: () => EntityRef[];
  /** the entries named in a passage, by the matcher that colours names */
  namedIn: (raw: string) => EntityRef[];
  /** an item made here: through the outbox, so it works offline */
  addItem: (item: { kind: "spark" | "question" | "task"; body: string; entities: string[]; passage: string; status: "open" | "deferred" }) => Promise<{ sent: boolean }>;
  /** after a fact is recorded: refresh what shows it, and say so (with Open and Undo) */
  recorded: (r: { entity: EntityRef; label: string; value: string; factId: string; undo: () => Promise<void> }) => void;
  saved: (kind: string, sent: boolean) => void;
  failed: (message: string) => void;
}

let suggestions: { world: string; at: number; data: Record<string, KindSuggestions> } | null = null;
/** Label and value suggestions per kind, fetched once a minute at most (offline: none, typing still works). */
async function loadSuggestions(world: string): Promise<Record<string, KindSuggestions>> {
  if (suggestions && suggestions.world === world && Date.now() - suggestions.at < 60_000) return suggestions.data;
  try {
    suggestions = { world, at: Date.now(), data: await factSuggestions(world) };
  } catch {
    suggestions = { world, at: Date.now(), data: suggestions?.world === world ? suggestions.data : {} };
  }
  return suggestions.data;
}

/** The item's text: your line followed by the passage as a quote; with no line typed, just the quote. */
export function itemBody(line: string, passage: string): string {
  const quote = passage
    .trim()
    .split("\n")
    .map((l) => `> ${l}`.trimEnd())
    .join("\n");
  return line.trim() ? `${line.trim()}\n\n${quote}` : quote;
}

export function passageActions(ctx: PassageContext, raw: string): PassageActions {
  const passage = raw.trim();
  void loadSuggestions(ctx.world);
  const kindOf = (kind: EntityKind) => suggestions?.data[kind];
  return {
    where: ctx.where,
    named: ctx.namedIn(raw),
    names: ctx.names,
    labels: (kind) => kindOf(kind)?.labels ?? [],
    values: (kind, label) => (kindOf(kind)?.values[norm(label)] ?? []).map((v) => v.value),
    // in a chapter: a fact with the same label, planned, is offered to be made canon here
    planned:
      ctx.where === "chapter"
        ? async (entityId, label) => {
            const { facts, journal_entries } = await getEntity(ctx.world, entityId);
            const f = facts.find((x) => x.standing === "planned" && norm(x.label) === norm(label));
            if (!f) return null;
            const j = f.planned_in_journal_id ? journal_entries?.[f.planned_in_journal_id] : undefined;
            return { id: f.id, value: f.value, where: j ? `Journal, ${journalDay(j.date)}` : "planned" };
          }
        : undefined,
    async recordFact(f) {
      try {
        const chapter = ctx.where === "chapter";
        const span = {
          ...(f.span.here && chapter ? { from_chapter_id: ctx.sourceId } : {}),
          ...(f.span.from !== null ? { from_time: f.span.from } : {}),
          ...(f.span.until !== null ? { until_time: f.span.until } : {}),
        };
        // from a chapter: established in it, the passage as evidence; from a journal entry: planned in it
        const where = chapter
          ? { established_in_chapter_id: ctx.sourceId, evidence: passage.slice(0, 5000) }
          : { planned_in_journal_id: ctx.sourceId, planned_evidence: passage.slice(0, 5000) };
        const made = await addFact(ctx.world, f.entity.id, {
          label: f.label, value: f.value, standing: f.makeCanon ? "canon" : f.standing, ...where, ...span,
          ...(f.makeCanon ? { make_canon: f.makeCanon } : {}),
        });
        ctx.recorded({
          entity: f.entity, label: f.label, value: f.value, factId: made.id,
          undo: async () => {
            const { deleteFact, updateFact } = await import("../bible");
            if (f.makeCanon) await updateFact(ctx.world, made, { standing: "planned", established_in_chapter_id: null, evidence: null, from_chapter_id: null });
            else await deleteFact(ctx.world, made.id);
          },
        });
      } catch (e) {
        ctx.failed((e as Error).message);
      }
    },
    async saveItem(i) {
      try {
        const { sent } = await ctx.addItem({ kind: i.kind, body: itemBody(i.line, passage), entities: i.entities, passage, status: i.park ? "deferred" : "open" });
        ctx.saved(i.kind, sent);
      } catch (e) {
        ctx.failed((e as Error).message);
      }
    },
  };
}
