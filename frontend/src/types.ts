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
}

export interface World {
  id: string;
  name: string;
  slug: string;
  role: string;
  projects: Project[];
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

export type EntityKind = "character" | "place" | "term" | "faction" | "object" | "other";

export const ENTITY_KINDS: { value: EntityKind; label: string; plural: string }[] = [
  { value: "character", label: "Character", plural: "Characters" },
  { value: "place", label: "Place", plural: "Places" },
  { value: "term", label: "Term", plural: "Terms" },
  { value: "faction", label: "Faction", plural: "Factions" },
  { value: "object", label: "Object", plural: "Objects" },
  { value: "other", label: "Other", plural: "Other" },
];

export interface EntityRef {
  id: string;
  name: string;
  kind: EntityKind;
}

export interface Entity extends EntityRef {
  aliases: string[];
  body: string;
  version: number;
  updated_at: string;
  mention_count: number;
}

export interface Mention {
  entity_id: string;
  entity_name: string;
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
