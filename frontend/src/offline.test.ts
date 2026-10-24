import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { localDb } from "./localdb";
import {
  dropDraft,
  getDraft,
  lastSynced,
  localChapter,
  localRevisions,
  localSummary,
  queueRevision,
  saveDraft,
  sendDrafts,
  sendPendingRevisions,
  syncWorld,
} from "./offline";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const chapter = (id: string, body = "text") => ({ id, title: id, body, version: 1, mentions: [], harvest_notes: [] });
const rev = (id: string, chapterId: string, minute: number) => ({
  id, chapter_id: chapterId, version: 1, title: "t", body: `body ${id}`, reason: "autosnap", label: null, words: 2,
  created_at: `2026-10-21T10:${String(minute).padStart(2, "0")}:00Z`,
});

beforeEach(async () => {
  await Promise.all([localDb.chapters.clear(), localDb.revisions.clear(), localDb.kv.clear(), localDb.drafts.clear(),
                     localDb.pendingRevisions.clear()]);
});
afterEach(() => vi.unstubAllGlobals());

describe("syncWorld", () => {
  it("keeps every chapter and only the last 30 snapshots of each", async () => {
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      urls.push(url);
      return Promise.resolve(json(200, {
        now: "2026-10-21T12:00:00Z",
        chapters: [chapter("a"), chapter("b")],
        revisions: Array.from({ length: 35 }, (_, i) => rev(`r${i}`, "a", i)),
        chapter_ids: ["a", "b"],
      }));
    }));
    expect(await syncWorld("coast")).toBe(true);
    expect(urls).toEqual(["/api/worlds/coast/offline"]);
    expect((await localChapter("a"))?.world).toBe("coast");
    const revs = await localRevisions("a");
    expect(revs).toHaveLength(30);
    expect(revs[0].id).toBe("r34");
    expect(revs.at(-1)?.id).toBe("r5");
    expect(await localSummary("coast")).toEqual({ chapters: 2, revisions: 30 });
    expect(await lastSynced("coast")).toBe("2026-10-21T12:00:00Z");
  });

  it("asks only for what changed since, and drops chapters that are gone", async () => {
    await localDb.chapters.bulkPut([{ ...chapter("a"), world: "coast" }, { ...chapter("b"), world: "coast" }] as never);
    await localDb.revisions.put({ ...rev("old", "b", 1), chapterId: "b" } as never);
    await localDb.kv.put({ key: "synced:coast", value: "2026-10-21T12:00:00Z" });
    const urls: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      urls.push(url);
      return Promise.resolve(json(200, { now: "2026-10-21T13:00:00Z", chapters: [chapter("a", "newer")], revisions: [], chapter_ids: ["a"] }));
    }));
    await syncWorld("coast");
    expect(urls[0]).toBe("/api/worlds/coast/offline?since=2026-10-21T12%3A00%3A00Z");
    expect((await localChapter("a"))?.body).toBe("newer");
    expect(await localChapter("b")).toBeUndefined();
    expect(await localRevisions("b")).toEqual([]);
  });

  it("reports offline instead of failing", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    expect(await syncWorld("coast")).toBe(false);
  });
});

describe("drafts and offline snapshots", () => {
  it("drops a draft only when the server has exactly that text", async () => {
    await saveDraft({ chapterId: "a", world: "coast", title: "A", body: "typed more", baseVersion: 3 });
    await dropDraft("a", "typed");
    expect((await getDraft("a"))?.body).toBe("typed more");
    await dropDraft("a", "typed more");
    expect(await getDraft("a")).toBeUndefined();
  });

  it("sends snapshots made offline once there is a connection", async () => {
    await queueRevision({ world: "coast", chapterId: "a", reason: "restore", label: "before", body: "replaced text" });
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await sendPendingRevisions();
    expect(await localDb.pendingRevisions.count()).toBe(1);
    const sent: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn((_u: string, init: RequestInit) => {
      sent.push(JSON.parse(String(init.body)));
      return Promise.resolve(json(201, { id: "x", skipped: false }));
    }));
    await sendPendingRevisions();
    expect(sent).toEqual([{ reason: "restore", label: "before", body: "replaced text" }]);
    expect(await localDb.pendingRevisions.count()).toBe(0);
  });

  it("keeps drafts and offline snapshots while the server is restarting", async () => {
    await saveDraft({ chapterId: "a", world: "coast", title: "A", body: "not saved yet", baseVersion: 3 });
    await queueRevision({ world: "coast", chapterId: "a", reason: "restore", label: "before", body: "replaced text" });
    // nginx answers 502 for the minute a new version is starting
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("<html>Bad Gateway</html>", { status: 502 }))));
    await expect(sendDrafts("coast")).rejects.toThrow(/may be restarting/);
    await sendPendingRevisions();
    expect((await getDraft("a"))?.body).toBe("not saved yet");
    expect(await localDb.pendingRevisions.count()).toBe(1);
  });
});
