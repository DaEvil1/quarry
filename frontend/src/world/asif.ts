// "Read as if accepted" (docs/SPEC.md §13.6.1): the book with an experiment's drafts in place of the range it would
// replace, or at the place it adds at. Worked out from the chapters kept on the device, so it reads offline too.

interface Chap {
  id: string;
  state: "current" | "experiment" | "retired";
  position: number;
  project: string;
  experiment_item_id: string | null;
  experiment?: { id: string; range: { id: string }[]; insert: { chapter_id: string; side: "before" | "after" } | null } | null;
}

/** The current chapters of a project in order, with experiment `item`'s drafts in place of its range. */
export function asIfAccepted<C extends Chap>(chapters: C[], project: string, item: string | null): (C & { draft?: boolean })[] {
  const book = chapters.filter((c) => c.project === project && c.state === "current").sort((a, b) => a.position - b.position);
  if (!item) return book;
  const drafts = chapters.filter((c) => c.experiment_item_id === item && c.state === "experiment").sort((a, b) => a.position - b.position);
  const x = drafts[0]?.experiment;
  if (!x || !drafts.length) return book;
  const range = new Set(x.range.map((r) => r.id));
  let at = book.findIndex((c) => range.has(c.id));
  if (at < 0 && x.insert) {
    const i = book.findIndex((c) => c.id === x.insert!.chapter_id);
    at = i < 0 ? book.length : i + (x.insert.side === "after" ? 1 : 0);
  } else if (at < 0) at = book.length;
  const stay = book.filter((c) => !range.has(c.id));
  const before = book.slice(0, at).filter((c) => !range.has(c.id)).length;
  return [...stay.slice(0, before), ...drafts.map((d) => ({ ...d, draft: true })), ...stay.slice(before)];
}
