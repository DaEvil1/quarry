// Bible calls, and a copy of each world's names kept on the device so tagging a capture works offline.

import { ApiError, del, get, patch, post } from "./api";
import { localDb } from "./localdb";
import type {
  Entity,
  EntityDetail,
  EntityKind,
  EntityRef,
  Fact,
  NearMissGroup,
  RelationType,
  Relationship,
  SourceTable,
  Standing,
} from "./types";

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export async function listEntities(world: string): Promise<Entity[]> {
  const list = await get<Entity[]>(`${base(world)}/entities`);
  await saveNames(world, list);
  return list;
}

export const getEntity = (world: string, id: string) => get<EntityDetail>(`${base(world)}/entities/${id}`);

export const createEntity = (world: string, body: { name: string; kind: EntityKind; aliases?: string[]; body?: string }) =>
  post<Entity>(`${base(world)}/entities`, body);

/** The entry changed on another device since it was loaded here; `current` is the server's copy. */
export class EntityConflict extends Error {
  constructor(public current: Entity) {
    super("This entry changed on another device. Showing the newer version.");
  }
}

export async function updateEntity(
  world: string,
  entity: Pick<Entity, "id" | "version">,
  changes: Partial<Pick<Entity, "name" | "kind" | "aliases" | "body" | "summary" | "match_case" | "first_name_alias" | "exclusions">>,
): Promise<Entity> {
  try {
    return await patch<Entity>(`${base(world)}/entities/${entity.id}`, { base_version: entity.version, ...changes });
  } catch (e) {
    const current = e instanceof ApiError && e.status === 409 ? (e.body as { entity?: Entity } | null)?.entity : null;
    if (current) throw new EntityConflict(current);
    throw e;
  }
}

export const deleteEntity = (world: string, id: string) => del(`${base(world)}/entities/${id}`);

export const nearMisses = (world: string) => get<NearMissGroup[]>(`${base(world)}/near-misses`);
export const nearMissCount = (world: string) => get<{ words: number }>(`${base(world)}/near-misses/count`);

/** The three fixes for a word that looks like a misspelled name. */
export const fixes = {
  replace: (world: string, token: string, entityId: string, source?: { table: SourceTable; id: string }) =>
    post<{ replaced: number }>(`${base(world)}/near-misses/replace`, {
      token,
      entity_id: entityId,
      ...(source ? { source_table: source.table, source_id: source.id } : {}),
    }),
  async addSpelling(world: string, token: string, entityId: string): Promise<void> {
    const { entity } = await getEntity(world, entityId);
    await updateEntity(world, entity, { aliases: [...entity.aliases, token] });
  },
  notATypo: (world: string, token: string) => post(`${base(world)}/name-ignores`, { token }),
};

export const linkItem = (world: string, itemId: string, entityId: string) =>
  post(`${base(world)}/items/${itemId}/links`, { entity_id: entityId });
export const unlinkItem = (world: string, itemId: string, entityId: string) =>
  del(`${base(world)}/items/${itemId}/links/${entityId}`);

async function saveNames(world: string, list: Entity[]): Promise<void> {
  try {
    const names: EntityRef[] = list.map(({ id, name, kind }) => ({ id, name, kind }));
    await localDb.kv.put({ key: `names:${world}`, value: names });
  } catch {
    /* storage unavailable */
  }
}

/** The world's names: from the server when online, else the copy on this device. */
export async function entityNames(world: string): Promise<EntityRef[]> {
  try {
    return (await listEntities(world)).map(({ id, name, kind }) => ({ id, name, kind }));
  } catch {
    try {
      return ((await localDb.kv.get(`names:${world}`))?.value as EntityRef[] | undefined) ?? [];
    } catch {
      return [];
    }
  }
}

/** Where a mention lives in the app. */
export function sourceLink(world: string, table: SourceTable, id: string) {
  switch (table) {
    case "item":
      return { name: "item", params: { world, id } };
    case "decision":
      return { name: "decisions", params: { world } };
    case "journal":
      return { name: "journal", params: { world }, hash: `#entry-${id}` };
    case "entity":
      return { name: "entity", params: { world, id } };
    case "chapter":
      return { name: "chapter", params: { world, id } };
  }
}

// ---- the world model: facts, relationship types, relationships ----

export const factSuggestions = (world: string) => get<Record<string, string[]>>(`${base(world)}/fact-suggestions`);
export const addFact = (
  world: string,
  entityId: string,
  body: { label: string; value: string; standing?: Standing; evidence?: string | null; established_in_chapter_id?: string | null },
) => post<Fact>(`${base(world)}/entities/${entityId}/facts`, body);
export const updateFact = (world: string, fact: Pick<Fact, "id" | "version">, changes: Partial<Omit<Fact, "id" | "version">>) =>
  patch<Fact>(`${base(world)}/facts/${fact.id}`, { base_version: fact.version, ...changes });
export const deleteFact = (world: string, id: string) => del(`${base(world)}/facts/${id}`);

export const relationTypes = (world: string) => get<RelationType[]>(`${base(world)}/relation-types`);
export const addRelationType = (world: string, body: { a_kind: string; b_kind: string; label: string; reverse_label: string | null }) =>
  post<RelationType>(`${base(world)}/relation-types`, body);
export const updateRelationType = (world: string, id: string, changes: { label?: string; reverse_label?: string | null }) =>
  patch<RelationType>(`${base(world)}/relation-types/${id}`, changes);
export const deleteRelationType = (world: string, id: string) => del(`${base(world)}/relation-types/${id}`);

export const addRelationship = (
  world: string,
  body: { type_id: string; a_id: string; b_id: string; standing?: Standing; note?: string | null; established_in_chapter_id?: string | null; evidence?: string | null },
) => post<Relationship>(`${base(world)}/relationships`, body);
export const updateRelationship = (world: string, r: Pick<Relationship, "id" | "version">, changes: { standing?: Standing; note?: string | null; type_id?: string }) =>
  patch<Relationship>(`${base(world)}/relationships/${r.id}`, { base_version: r.version, ...changes });
export const deleteRelationship = (world: string, id: string) => del(`${base(world)}/relationships/${id}`);

/** The ways two kinds can be related, read from the first one's side: types that fit forward (it is A) or
 * backward (it is B, read with the reverse label). Symmetric types appear once. */
export function typeOptions(types: RelationType[], from: string, to: string): { type: RelationType; reads: string; forward: boolean }[] {
  const fits = (kind: string, side: string) => side === "*" || side === kind;
  const out: { type: RelationType; reads: string; forward: boolean }[] = [];
  for (const t of types) {
    if (fits(from, t.a_kind) && fits(to, t.b_kind)) out.push({ type: t, reads: t.label, forward: true });
    else if (fits(to, t.a_kind) && fits(from, t.b_kind)) out.push({ type: t, reads: t.reverse_label ?? t.label, forward: false });
  }
  // the specific ones first, "linked to" last
  return out.sort((a, b) => Number(a.type.a_kind === "*" && a.type.b_kind === "*") - Number(b.type.a_kind === "*" && b.type.b_kind === "*"));
}
