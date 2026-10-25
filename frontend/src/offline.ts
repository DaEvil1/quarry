// The offline copy of the manuscript. When online, each world opened on this device is synced in the background:
// every chapter, and the last 30 snapshots of each. The chapter page and History fall back to this copy when the
// server can't be reached, and text typed but not yet saved is kept here as a draft.

import { ApiError, get, patch, post, unreachable } from "./api";
import {
  localDb,
  type Draft,
  type LocalChapter,
  type LocalRevision,
  type PendingRevision,
} from "./localdb";
import { countWords } from "./words";
import type { Chapter, ChapterInfo, Experiment, Manuscript, RevisionInfo } from "./manuscript";

export const LOCAL_REVISIONS = 30;

interface Pack {
  now: string;
  chapters: Chapter[];
  revisions: (LocalRevision & { chapter_id: string })[];
  chapter_ids: string[];
}

const syncedKey = (world: string) => `synced:${world}`;

/** Ask the browser to keep Quarry's storage even when space runs low (Chrome on Android grants it to installed apps). */
export async function persistStorage(): Promise<boolean> {
  try {
    if (await navigator.storage?.persisted?.()) return true;
    return (await navigator.storage?.persist?.()) ?? false;
  } catch {
    return false;
  }
}

export async function storageInfo(): Promise<{ persisted: boolean; usage: number | null }> {
  try {
    const persisted = (await navigator.storage?.persisted?.()) ?? false;
    const estimate = await navigator.storage?.estimate?.();
    return { persisted, usage: estimate?.usage ?? null };
  } catch {
    return { persisted: false, usage: null };
  }
}

/** Keep only the newest `LOCAL_REVISIONS` snapshots of a chapter. */
async function prune(chapterId: string): Promise<void> {
  const all = await localDb.revisions.where("chapterId").equals(chapterId).sortBy("created_at");
  const extra = all.length - LOCAL_REVISIONS;
  if (extra > 0) await localDb.revisions.bulkDelete(all.slice(0, extra).map((r) => r.id));
}

/** Bring the offline copy of a world up to date. Returns false when the server can't be reached. */
export async function syncWorld(world: string): Promise<boolean> {
  try {
    const since = (await localDb.kv.get(syncedKey(world)))?.value as string | undefined;
    const pack = await get<Pack>(`/api/worlds/${encodeURIComponent(world)}/offline${since ? `?since=${encodeURIComponent(since)}` : ""}`);
    await localDb.transaction("rw", [localDb.chapters, localDb.revisions, localDb.kv], async () => {
      await localDb.chapters.bulkPut(pack.chapters.map((c) => ({ ...c, world })));
      await localDb.revisions.bulkPut(
        pack.revisions.map(({ chapter_id, ...r }) => ({ ...r, chapterId: chapter_id })),
      );
      const keep = new Set(pack.chapter_ids);
      const gone = (await localDb.chapters.where("world").equals(world).primaryKeys()).filter((id) => !keep.has(id));
      if (gone.length) {
        await localDb.chapters.bulkDelete(gone);
        await localDb.revisions.where("chapterId").anyOf(gone).delete();
      }
      await localDb.kv.put({ key: syncedKey(world), value: pack.now });
    });
    for (const id of new Set(pack.revisions.map((r) => r.chapter_id))) await prune(id);
    await sendPendingRevisions();
    return true;
  } catch (e) {
    if (e instanceof ApiError && !unreachable(e)) throw e;
    return false;
  }
}

export async function lastSynced(world: string): Promise<string | null> {
  try {
    return ((await localDb.kv.get(syncedKey(world)))?.value as string | undefined) ?? null;
  } catch {
    return null;
  }
}

export async function localSummary(world: string): Promise<{ chapters: number; revisions: number }> {
  const ids = await localDb.chapters.where("world").equals(world).primaryKeys();
  const revisions = ids.length ? await localDb.revisions.where("chapterId").anyOf(ids).count() : 0;
  return { chapters: ids.length, revisions };
}

export async function clearOfflineCopy(): Promise<void> {
  await localDb.transaction("rw", [localDb.chapters, localDb.revisions, localDb.kv], async () => {
    await localDb.chapters.clear();
    await localDb.revisions.clear();
    const keys = (await localDb.kv.toCollection().primaryKeys()).filter((k) => String(k).startsWith("synced:"));
    await localDb.kv.bulkDelete(keys);
  });
}

/** The open experiments among a project's chapters kept on the device: each draft carries its experiment. */
function localExperiments(all: LocalChapter[], strip: (c: LocalChapter) => ChapterInfo): Experiment[] {
  const out = new Map<string, Experiment>();
  for (const c of all.filter((x) => x.state === "experiment").sort((a, b) => a.position - b.position)) {
    const e = c.experiment;
    if (!e) continue;
    const x = out.get(e.id) ?? { id: e.id, title: e.title, status: e.status, range: e.range, range_words: e.range.reduce((n, r) => n + r.words, 0), insert: e.insert, drafts: [], words: 0, lost: e.lost, replaced_by: e.replaced_by };
    x.drafts.push(strip(c));
    x.words += countWords(c.body);
    out.set(e.id, x);
  }
  return [...out.values()];
}

/** A project's manuscript from the copy on this device (when the server can't be reached). */
export async function localManuscript(world: string, project: string): Promise<Manuscript> {
  const all = (await localDb.chapters.where("world").equals(world).toArray()).filter((c) => c.project === project);
  const strip = ({ body, mentions, harvest_notes, experiment, experiment_status, world: _w, ...info }: LocalChapter) =>
    ({ ...info, words: countWords(body) }) as ChapterInfo;
  const current = all.filter((c) => c.state === "current").sort((a, b) => a.position - b.position).map(strip);
  const tally = new Map<string, number>();
  for (const c of current) if (c.pov) tally.set(c.pov.name, (tally.get(c.pov.name) ?? 0) + 1);
  // the statuses its chapters have (the full list, with those no chapter has, needs the server)
  const statuses = [...new Map(all.flatMap((c) => (c.status ? [[c.status.id, c.status] as const] : []))).values()].sort(
    (a, b) => a.position - b.position,
  );
  const group = (id: string | null) => current.filter((c) => (c.status?.id ?? null) === id);
  return {
    chapters: current,
    experiments: localExperiments(all, strip),
    pov_tally: [...tally.entries()].sort((a, b) => b[1] - a[1]).map(([name, chapters]) => ({ name, chapters })),
    words: current.reduce((n, c) => n + c.words, 0),
    retired: all.filter((c) => c.state === "retired").length,
    statuses,
    status_tally: [...statuses, null].map((s) => {
      const g = group(s?.id ?? null);
      return { id: s?.id ?? null, label: s?.label ?? null, chapters: g.length, words: g.reduce((n, c) => n + c.words, 0) };
    }),
  };
}

/** Every chapter of a world kept on this device (for reading an entry's thread offline). */
export async function localChapters(world: string): Promise<LocalChapter[]> {
  try {
    return await localDb.chapters.where("world").equals(world).toArray();
  } catch {
    return [];
  }
}

// ---- one chapter ----

export async function cacheChapter(world: string, chapter: Chapter): Promise<void> {
  try {
    await localDb.chapters.put({ ...chapter, world });
  } catch {
    /* storage unavailable */
  }
}

export async function localChapter(id: string): Promise<LocalChapter | undefined> {
  try {
    return await localDb.chapters.get(id);
  } catch {
    return undefined;
  }
}

export async function localRevisions(chapterId: string): Promise<RevisionInfo[]> {
  const rows = await localDb.revisions.where("chapterId").equals(chapterId).sortBy("created_at");
  return rows.reverse().map(({ id, version, title, reason, label, words, created_at }) => ({
    id, version, title, reason, label, words, created_at,
  }));
}

export async function localRevision(id: string): Promise<(RevisionInfo & { body: string }) | undefined> {
  return localDb.revisions.get(id);
}

// ---- drafts: text written here, not yet confirmed by the server ----

export async function saveDraft(draft: Omit<Draft, "savedAt">): Promise<void> {
  try {
    await localDb.drafts.put({ ...draft, savedAt: new Date().toISOString() });
  } catch {
    /* storage unavailable: the editor still holds the text */
  }
}

export async function getDraft(chapterId: string): Promise<Draft | undefined> {
  try {
    return await localDb.drafts.get(chapterId);
  } catch {
    return undefined;
  }
}

export async function dropDraft(chapterId: string, body?: string): Promise<void> {
  try {
    const d = await localDb.drafts.get(chapterId);
    // only when the server has exactly this text; something typed meanwhile stays
    if (d && (body === undefined || d.body === body)) await localDb.drafts.delete(chapterId);
  } catch {
    /* nothing to drop */
  }
}

/**
 * Send the text this device still holds for a world's chapters (drafts the server hasn't confirmed), before a find
 * and replace looks at them. A draft written on top of an older version becomes a conflict copy, as when the
 * chapter is opened. Throws when the server can't be reached.
 */
export async function sendDrafts(world: string): Promise<void> {
  const drafts = await localDb.drafts.where("world").equals(world).toArray();
  for (const d of drafts) {
    try {
      await patch(`/api/worlds/${encodeURIComponent(world)}/chapters/${d.chapterId}`, {
        base_version: d.baseVersion,
        title: d.title || undefined,
        body: d.body,
      });
      await localDb.drafts.delete(d.chapterId);
    } catch (e) {
      if (!(e instanceof ApiError) || unreachable(e)) throw e;
      if (e.status === 409) {
        const current = (e.body as { chapter?: { body: string } } | null)?.chapter;
        if (current && current.body !== d.body) {
          await post(`/api/worlds/${encodeURIComponent(world)}/chapters/${d.chapterId}/revisions`, {
            reason: "conflict",
            label: "Written on this device while another version was saved",
            body: d.body,
          });
        }
      }
      // the chapter is gone, or its text is kept as a conflict copy now
      await localDb.drafts.delete(d.chapterId);
    }
  }
}

// ---- checkpoints, for showing the changes since one ----

export interface Checkpoint {
  id: string;
  label: string;
  created_at: string;
}

/** A chapter's labelled checkpoints, newest first: from the server, or (offline) the ones on this device. */
export async function labelledCheckpoints(world: string, chapterId: string): Promise<{ list: Checkpoint[]; local: boolean }> {
  const labelled = (rows: { id: string; label: string | null; reason: string; created_at: string }[]) =>
    rows
      .filter((r) => r.label && r.reason !== "conflict")
      .map(({ id, label, created_at }) => ({ id, label: label!, created_at }))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  try {
    return { list: labelled(await get<RevisionInfo[]>(`/api/worlds/${encodeURIComponent(world)}/chapters/${chapterId}/revisions`)), local: false };
  } catch (e) {
    if (!unreachable(e)) throw e;
    const local = await localDb.revisions.where("chapterId").equals(chapterId).toArray();
    const kept = await localDb.checkpoints.where("chapterId").equals(chapterId).toArray();
    const seen = new Set(local.map((r) => r.id));
    return { list: labelled([...local, ...kept.filter((k) => !seen.has(k.id)).map((k) => ({ ...k, reason: "checkpoint" }))]), local: true };
  }
}

/** A checkpoint's text: from this device if it is here, else fetched once and kept (older than the last 30). */
export async function checkpointBody(world: string, chapterId: string, cp: Checkpoint): Promise<string | null> {
  const here = (await localDb.revisions.get(cp.id)) ?? (await localDb.checkpoints.get(cp.id));
  if (here) return here.body;
  try {
    const r = await get<RevisionInfo & { body: string }>(`/api/worlds/${encodeURIComponent(world)}/revisions/${cp.id}`);
    await localDb.checkpoints.put({ id: r.id, chapterId, label: cp.label, body: r.body, created_at: r.created_at });
    return r.body;
  } catch (e) {
    if (unreachable(e)) return null;
    throw e;
  }
}

// ---- snapshots made offline ----

export async function queueRevision(rev: Omit<PendingRevision, "id">): Promise<void> {
  await localDb.pendingRevisions.put({ ...rev, id: crypto.randomUUID() });
}

/** Send snapshots made offline (the text an offline restore replaced). */
export async function sendPendingRevisions(): Promise<void> {
  for (const r of await localDb.pendingRevisions.toArray()) {
    try {
      await post(`/api/worlds/${encodeURIComponent(r.world)}/chapters/${r.chapterId}/revisions`, {
        reason: r.reason,
        label: r.label,
        body: r.body,
      });
      await localDb.pendingRevisions.delete(r.id);
    } catch (e) {
      if (!(e instanceof ApiError) || unreachable(e)) return;
      // the chapter is gone or the snapshot is refused: nothing more to do with it
      await localDb.pendingRevisions.delete(r.id);
    }
  }
}
