// What a character is (docs/SPEC.md §13.3): the species from "is a" and the outward forms from "appears as", read by
// label from the character's side the way the family tree reads parent types; and who possesses them (§13.5). Worked
// out from the cards (offline too), following "as of": pass a card as it reads at a chapter.

import type { EntityRef } from "../types";
import type { Card } from "./cards";
import { holds, type IndexOf } from "./time";

const IS_A = /^is an?$/i;
const APPEARS = /^appears as( an?)?$/i;
const POSSESSED = /^possessed by$/i;
const clean = (s: string) => s.trim().replace(/\s+/g, " ");

type Rel = Card["relations"][number];
export const isSpecies = (r: Rel) => r.other.kind === "species" && IS_A.test(clean(r.label));
export const isGuise = (r: Rel) => r.other.kind === "species" && APPEARS.test(clean(r.label));
export const isPossession = (r: Rel) => POSSESSED.test(clean(r.label));
/** Read by label to show beside or under the name, so the card's list of relationships leaves them out. */
export const shownByName = (r: Rel) => isSpecies(r) || isGuise(r) || isPossession(r);

/** A character's species and outward forms, as its card reads (several side by side; canon and otherwise alike). */
export function speciesOf(card: Card | undefined): { is: EntityRef[]; appears: EntityRef[] } {
  if (!card || card.kind !== "character") return { is: [], appears: [] };
  const uniq = (xs: EntityRef[]) => xs.filter((x, i) => xs.findIndex((y) => y.id === x.id) === i);
  return {
    is: uniq(card.relations.filter((r) => isSpecies(r) && r.standing !== "rumour").map((r) => r.other)),
    appears: uniq(card.relations.filter((r) => isGuise(r) && r.standing !== "rumour").map((r) => r.other)),
  };
}

/** "selkie · appears as human", or "" when nothing is recorded. */
export function speciesText(card: Card | undefined): string {
  const { is, appears } = speciesOf(card);
  return [...is.map((s) => s.name), ...appears.map((s) => `appears as ${s.name}`)].join(" · ");
}

/** Who possesses this character, as its card reads. */
export function possessors(card: Card | undefined): EntityRef[] {
  if (!card || card.kind !== "character") return [];
  return card.relations.filter((r) => isPossession(r) && r.standing !== "rumour").map((r) => r.other);
}

/** The species a character is at the end of the story (chapter index `last`, or every recorded one with no chapters),
 * for the characters table's column. */
export function speciesAtEnd(card: Card, last: number | null, indexOf: IndexOf): string[] {
  if (card.kind !== "character") return [];
  const span = (r: Rel) => ({ from_chapter_id: r.from, until_chapter_id: r.until });
  const out: string[] = [];
  for (const r of card.relations) {
    if (!isSpecies(r) || r.standing !== "canon") continue;
    if (last !== null && !holds(span(r), last, indexOf)) continue;
    if (!out.includes(r.other.name)) out.push(r.other.name);
  }
  return out;
}

/** The column's key in the address (`f=@species:selkie`, `group=@species`): never a fact label. */
export const SPECIES_COLUMN = "@species";

/** Graph colouring by species (docs/SPEC.md §13.3): each character's species as of a chapter (the first recorded,
 * canon or planned), and a colour per species from a fixed set, in order of how many characters each has; the rest
 * grey. Species entries take their own colour. */
export function speciesColours(
  data: { nodes: { id: string; name: string; kind: string }[]; edges: { a: string; b: string; label: string; reverse_label: string | null; standing: string; from_chapter_id: string | null; until_chapter_id: string | null }[] },
  asOf: number | null,
  indexOf: IndexOf,
): { of: Map<string, string>; legend: { id: string; name: string; count: number; colour: string | null }[] } {
  const kind = new Map(data.nodes.map((n) => [n.id, n.kind]));
  const name = new Map(data.nodes.map((n) => [n.id, n.name]));
  const of = new Map<string, string>();
  for (const e of data.edges) {
    if (e.standing === "rumour" || (asOf !== null && !holds(e, asOf, indexOf))) continue;
    // read from the character's side
    const [who, what, reads] = kind.get(e.a) === "character" && kind.get(e.b) === "species" ? [e.a, e.b, e.label] : kind.get(e.b) === "character" && kind.get(e.a) === "species" ? [e.b, e.a, e.reverse_label ?? e.label] : [null, null, ""];
    if (who && what && IS_A.test(clean(reads)) && !of.has(who)) of.set(who, what);
  }
  const counts = new Map<string, number>();
  for (const s of of.values()) counts.set(s, (counts.get(s) ?? 0) + 1);
  const ranked = [...counts].sort((a, b) => b[1] - a[1] || (name.get(a[0]) ?? "").localeCompare(name.get(b[0]) ?? ""));
  const legend = ranked.map(([id, count], i) => ({ id, name: name.get(id) ?? "?", count, colour: i < SPECIES_PALETTE.length ? SPECIES_PALETTE[i]! : null }));
  return { of, legend };
}

/** Eight colours that read on both themes, for the graph's species. */
export const SPECIES_PALETTE = ["#d9822b", "#2f9e7e", "#7b61d1", "#c2410c", "#2b7bb9", "#b7a12f", "#c03d8c", "#5c9a2e"];
