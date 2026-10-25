export type ProjectKind = "novel" | "novella" | "short" | "other";

export const PROJECT_KINDS: { value: ProjectKind; label: string }[] = [
  { value: "novel", label: "Novel" },
  { value: "novella", label: "Novella" },
  { value: "short", label: "Short story" },
  { value: "other", label: "Other" },
];

export interface Project {
  id: string;
  name: string;
  slug: string;
  kind: ProjectKind;
  position: number;
  /** chapters without an entry, between two that name it, that make a gap on its mentions strip */
  gap_chapters: number;
}

export interface World {
  id: string;
  name: string;
  slug: string;
  role: string;
  projects: Project[];
  /** what in-world time is counted in, one and several (docs/SPEC.md §13.1.1) */
  time_unit?: string;
  time_units?: string;
}

export interface User {
  id: string;
  display_name: string;
}

export interface Me {
  user: User;
  worlds: World[];
}

export interface PasskeyInfo {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
}

/** What the backend sends to start a WebAuthn ceremony. */
export interface Ceremony<T> {
  challenge_id: string;
  options: T;
}

export function kindLabel(kind: ProjectKind): string {
  return PROJECT_KINDS.find((k) => k.value === kind)?.label ?? kind;
}

export type ItemKind = "spark" | "question" | "task" | "experiment";
export type ItemStatus = "open" | "accepted" | "rejected" | "harvested" | "deferred";
export type CloseStatus = Exclude<ItemStatus, "open">;

export const CAPTURE_KINDS: { value: Exclude<ItemKind, "experiment">; label: string }[] = [
  { value: "spark", label: "Spark" },
  { value: "question", label: "Question" },
  { value: "task", label: "Task" },
];

export const STATUS_LABELS: Record<ItemStatus, string> = {
  open: "Open",
  accepted: "Accepted",
  rejected: "Rejected",
  harvested: "Harvested",
  deferred: "Deferred",
};

export type EntityKind = "character" | "place" | "faction" | "culture" | "species" | "event" | "object" | "term" | "other";

export const ENTITY_KINDS: { value: EntityKind; label: string; plural: string }[] = [
  { value: "character", label: "Character", plural: "Characters" },
  { value: "place", label: "Place", plural: "Places" },
  { value: "faction", label: "Faction", plural: "Factions" },
  { value: "culture", label: "Culture", plural: "Cultures" },
  { value: "species", label: "Species", plural: "Species" },
  { value: "event", label: "Event", plural: "Events" },
  { value: "object", label: "Object", plural: "Objects" },
  { value: "term", label: "Term", plural: "Terms" },
  { value: "other", label: "Other", plural: "Other" },
];

/** A character's gender, read by the family tree for its words; null is "not set" (docs/SPEC.md §12.5). */
export type Gender = "female" | "male" | "nonbinary";

export const GENDERS: { value: Gender | null; label: string }[] = [
  { value: null, label: "not set" },
  { value: "female", label: "female" },
  { value: "male", label: "male" },
  { value: "nonbinary", label: "nonbinary" },
];

export interface EntityRef {
  id: string;
  name: string;
  kind: EntityKind;
}

export interface Entity extends EntityRef {
  aliases: string[];
  body: string;
  summary: string;
  match_case: boolean;
  first_name_alias: boolean;
  exclusions: string[];
  version: number;
  updated_at: string;
  mention_count: number;
  /** after a rename: the old name, kept as another name (docs/SPEC.md §11.1) */
  kept_alias?: string | null;
  /** its level: the project whose part of the bible it is in, or null for the world (docs/SPEC.md §12.4) */
  project: string | null;
  gender: Gender | null;
  /** in the bible's list: the projects whose current chapters name it */
  named_in: string[];
}

export type Standing = "canon" | "planned" | "rumour";

export interface Fact {
  id: string;
  entity_id: string;
  label: string;
  value: string;
  position: number;
  standing: Standing;
  evidence: string | null;
  note: string | null;
  established_in_chapter_id: string | null;
  from_chapter_id: string | null;
  until_chapter_id: string | null;
  from_time?: number | null;
  from_approx?: boolean;
  until_time?: number | null;
  until_approx?: boolean;
  outside_time?: boolean;
  version: number;
  /** after adding: the one-time "expect it on every …?" question (docs/SPEC.md §12.6.5) */
  prompt?: { kind: EntityKind; label: string; count: number } | null;
}

export interface RelationType {
  id: string;
  a_kind: EntityKind | "*";
  b_kind: EntityKind | "*";
  label: string;
  reverse_label: string | null;
  position: number;
  /** its relationships carry a role in the group on the B side (docs/SPEC.md §13.4) */
  has_role: boolean;
  used: number;
}

export interface Relationship {
  id: string;
  type_id: string;
  a: EntityRef;
  b: EntityRef;
  label: string;
  reverse_label: string | null;
  standing: Standing;
  evidence: string | null;
  note: string | null;
  established_in_chapter_id: string | null;
  from_chapter_id: string | null;
  until_chapter_id: string | null;
  from_time?: number | null;
  from_approx?: boolean;
  until_time?: number | null;
  until_approx?: boolean;
  outside_time?: boolean;
  /** the A side's role in the B side's group, and whether the type offers one */
  role?: string | null;
  has_role?: boolean;
  version: number;
  /** on an entry's page: how it reads from this entry, the entry on the other side, and which side this is */
  reads?: string;
  other?: EntityRef;
  side?: "a" | "b";
}

export interface Mention {
  entity_id: string;
  entity_name: string;
  entity_kind?: EntityKind;
  start: number;
  end: number;
  matched_text: string;
  kind: "exact" | "alias" | "near_miss";
}

export type SourceTable = "item" | "decision" | "journal" | "entity" | "chapter";

export interface Snippet {
  before: string;
  match: string;
  after: string;
}

export interface SourceRef {
  source_table: SourceTable;
  source_id: string;
  title: string;
  project: string | null;
  snippet: Snippet;
}

export interface EntityDetail {
  entity: Entity;
  mentions: (SourceRef & { count: number })[];
  unlinked: (SourceRef & { count: number })[];
  linked_items: { id: string; title: string; status: ItemStatus; project: string | null }[];
  near_misses: (SourceRef & { token: string })[];
  first_appearance: { project: string; chapter_id: string; title: string; position: number }[];
  decisions: { id: string; decided_on: string; text: string; project: string | null; tagged: boolean }[];
  facts: Fact[];
  relationships: Relationship[];
  chapter_titles: Record<string, string>;
}

export interface NearMissGroup {
  token: string;
  entity: { id: string; name: string };
  count: number;
  sources: SourceRef[];
}

export interface JournalEntry {
  id: string;
  entry_date: string;
  title: string | null;
  body: string;
  project: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Item {
  id: string;
  kind: ItemKind;
  title: string | null;
  body: string;
  status: ItemStatus;
  project: string | null;
  source: string | null;
  closed_note: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  entities: EntityRef[];
  mentions: Mention[];
}

export interface ItemCounts {
  open: number;
  deferred: number;
  open_by_project: Record<string, number>;
}

export interface Decision {
  id: string;
  decided_on: string;
  text: string;
  project: string | null;
  item_id: string | null;
  created_at: string;
  entities: EntityRef[];
}

/** "?project=-" on the API: items that belong to the whole world rather than one project. */
export const WORLD_ONLY = "-";

/** The first line of an item, for lists. */
export function firstLine(item: Pick<Item, "title" | "body">): string {
  return item.title || item.body.split("\n", 1)[0];
}

/** Today in the person's own time zone, as the API's date format. */
export function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** When a chapter (or an event) is set (docs/SPEC.md §13.1.1): a number with an optional end, a free label and
 * "about"; or outside time; or neither (not set). */
export interface TimeValue {
  time_at: number | null;
  time_end?: number | null;
  time_label?: string | null;
  time_approx?: boolean;
  outside_time?: boolean;
}

/** A chapter in story order: projects in their order, then chapters in theirs (docs/WORLD-MODEL.md §4), with when it
 * is set and its place on the clock (docs/SPEC.md §13.1.3). */
export interface StoryChapter extends Partial<TimeValue> {
  id: string;
  title: string;
  project: string;
  project_name: string;
  /** its place in book order (told order), from 0 */
  index: number;
  /** the chapter's point-of-view entry */
  pov?: string | null;
  /** its project's gap length */
  gap_chapters?: number;
  told_as?: "flashback" | "tale" | null;
  /** its own time, or the one it carries on from */
  set_time?: number | null;
  set_approx?: boolean;
  /** a tale or flashback with no time: set before the story */
  early?: boolean;
  /** its place in happened order; null outside time (absent from an older copy: book order) */
  clock?: number | null;
}

/** When a fact or relationship holds: from and/or until a chapter or a time; neither means throughout; outside time
 * means never on the clock (docs/SPEC.md §13.1.5, §13.1.8). */
export interface Span {
  from_chapter_id: string | null;
  until_chapter_id: string | null;
  from_time?: number | null;
  from_approx?: boolean;
  until_time?: number | null;
  until_approx?: boolean;
  outside_time?: boolean;
}

export interface Presence {
  entity_id: string;
  place: EntityRef;
  note: string | null;
}

export interface WhereCell {
  /** how often the chapter names it */
  count: number;
  recorded: EntityRef | null;
  note: string | null;
  derived: EntityRef | null;
  present: boolean;
  /** for a place: who is recorded "is at" there */
  people: EntityRef[];
}

export interface WhereRow {
  entity: EntityRef;
  /** picked by hand rather than through a kind */
  added: boolean;
  cells: Record<string, WhereCell>;
}

export interface WhereGrid {
  chapters: ({ id: string; title: string; project: string; project_name: string; pov: EntityRef | null; told_as?: "flashback" | "tale" | null; set_time?: number | null; set_approx?: boolean; early?: boolean; clock?: number | null; set_text?: string } & Partial<TimeValue>)[];
  rows: WhereRow[];
  events: Record<string, EntityRef[]>;
}
