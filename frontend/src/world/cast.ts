// Who a text names, for the side panel's cast: each entry with how often it is named, and the shared names nothing
// settles listed once with their claimants, as `Isolde? Marr · Senn` (docs/SPEC.md §14.10).

import type { Mention } from "../types";

export interface Named {
  id: string;
  name: string;
  kind: string | undefined;
  count: number;
}

export interface UnsettledName {
  /** the name as written, without a possessive ("Isolde") */
  form: string;
  claimants: { id: string; name: string; kind: string | undefined }[];
  /** the word of each claimant's name that tells them apart ("Marr", "Senn") */
  short: string[];
  count: number;
}

/** The word of each name that tells it apart from the others ("Marr", "Senn"), or the whole name. */
export function shortNames(names: string[]): string[] {
  const words = names.map((n) => n.split(/\s+/).filter(Boolean));
  return names.map((n, i) => {
    const others = new Set(words.filter((_, j) => j !== i).flat().map((w) => w.toLowerCase()));
    return words[i]!.find((w) => !others.has(w.toLowerCase())) ?? n;
  });
}

const base = (s: string) => s.replace(/(?:'s|’s)$/, "");

export function castOf(mentions: Mention[]): { named: Named[]; unsettled: UnsettledName[] } {
  const counts = new Map<string, Named>();
  // an ambiguous name is one mention per claimant at the same place
  const places = new Map<string, Mention[]>();
  for (const m of mentions) {
    if (m.kind === "near_miss") continue;
    if (m.kind === "ambiguous") {
      const at = `${m.start}:${m.end}`;
      places.set(at, [...(places.get(at) ?? []), m]);
      continue;
    }
    const c = counts.get(m.entity_id) ?? { id: m.entity_id, name: m.entity_name, kind: m.entity_kind, count: 0 };
    c.count++;
    counts.set(m.entity_id, c);
  }
  const groups = new Map<string, UnsettledName>();
  for (const ms of places.values()) {
    const claimants = ms.map((m) => ({ id: m.entity_id, name: m.entity_name, kind: m.entity_kind })).sort((a, b) => a.name.localeCompare(b.name));
    const form = base(ms[0]!.matched_text);
    const key = `${form.toLowerCase()}|${claimants.map((c) => c.id).join(",")}`;
    const g = groups.get(key) ?? { form, claimants, short: shortNames(claimants.map((c) => c.name)), count: 0 };
    g.count++;
    groups.set(key, g);
  }
  return {
    named: [...counts.values()].sort((a, b) => b.count - a.count),
    unsettled: [...groups.values()].sort((a, b) => b.count - a.count),
  };
}
