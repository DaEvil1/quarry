import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import { AUTOSAVE_MS, ChapterSaver, IDLE_MS, LONG_MS, RETRY_MS, type SaveStatus } from "./editor/saver";
import { ChapterConflict, type Chapter } from "./manuscript";

const chapter = (version: number, body = ""): Chapter =>
  ({ id: "c1", version, body, title: "One", mentions: [], harvest_notes: [] }) as unknown as Chapter;

function setup(save: (v: number, changes: { body?: string }) => Promise<Chapter>) {
  const calls = { save: [] as [number, { body?: string; title?: string }][], snapshots: [] as [string, unknown][] };
  const statuses: SaveStatus[] = [];
  const conflicts: [Chapter, string][] = [];
  const saver = new ChapterSaver(
    { version: 1 },
    {
      save: (v, c) => (calls.save.push([v, c]), save(v, c)),
      snapshot: (r, extra) => (calls.snapshots.push([r, extra]), Promise.resolve({})),
      now: () => Date.now(),
    },
    { saved: () => {}, conflict: (c, mine) => conflicts.push([c, mine]), status: (s) => statuses.push(s) },
  );
  return { saver, calls, statuses, conflicts };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("ChapterSaver", () => {
  it("autosaves once after typing stops, with the version it started from", async () => {
    let v = 1;
    const { saver, calls, statuses } = setup(async (_b, c) => chapter(++v, c.body));
    saver.edit({ body: "a" });
    saver.edit({ body: "ab" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS - 1);
    expect(calls.save).toEqual([]);
    await vi.advanceTimersByTimeAsync(1);
    expect(calls.save).toEqual([[1, { body: "ab" }]]);
    saver.edit({ body: "abc" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(calls.save[1]).toEqual([2, { body: "abc" }]);
    expect(statuses.at(-1)).toBe("saved");
  });

  it("keeps a snapshot after five idle minutes, not on every save", async () => {
    let v = 1;
    const { saver, calls } = setup(async (_b, c) => chapter(++v, c.body));
    saver.edit({ body: "draft" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(calls.snapshots).toEqual([]);
    await vi.advanceTimersByTimeAsync(IDLE_MS);
    expect(calls.snapshots).toEqual([["autosnap", {}]]);
    // nothing new written: no second snapshot
    await vi.advanceTimersByTimeAsync(IDLE_MS);
    expect(calls.snapshots).toHaveLength(1);
  });

  it("keeps a snapshot every 30 minutes of continuous writing", async () => {
    let v = 1;
    const { saver, calls } = setup(async (_b, c) => chapter(++v, c.body));
    for (let minute = 1; minute <= 31; minute++) {
      saver.edit({ body: `text ${minute}` });
      await vi.advanceTimersByTimeAsync(60_000);
    }
    expect(calls.snapshots.filter(([r]) => r === "autosnap")).toHaveLength(1);
    expect(LONG_MS).toBe(30 * 60_000);
  });

  it("checkpoint saves first, then keeps a labelled snapshot", async () => {
    const { saver, calls } = setup(async (_b, c) => chapter(2, c.body));
    saver.edit({ body: "x" });
    await saver.checkpoint("before the split");
    expect(calls.save).toHaveLength(1);
    expect(calls.snapshots).toEqual([["checkpoint", { label: "before the split" }]]);
  });

  it("offline: keeps the text, says so, and retries", async () => {
    let fail = true;
    const { saver, calls, statuses } = setup(async (_b, c) => {
      if (fail) throw new ApiError(0, "offline");
      return chapter(2, c.body);
    });
    saver.edit({ body: "written on the train" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(statuses.at(-1)).toBe("offline");
    expect(saver.dirty).toBe(true);
    fail = false;
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect(calls.save.at(-1)).toEqual([1, { body: "written on the train" }]);
    expect(saver.dirty).toBe(false);
    expect(statuses.at(-1)).toBe("saved");
  });

  it("conflict: keeps this device's text as a revision and takes the newer one", async () => {
    const theirs = chapter(5, "their text");
    const { saver, calls, conflicts, statuses } = setup(async () => {
      throw new ChapterConflict(theirs);
    });
    saver.edit({ body: "my text" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    expect(calls.snapshots).toEqual([["conflict", { body: "my text" }]]);
    expect(conflicts).toEqual([[theirs, "my text"]]);
    expect(statuses.at(-1)).toBe("conflict");
    expect(saver.dirty).toBe(false);
  });

  it("a retry whose text the server already has is saved, not a conflict", async () => {
    // the first try reached the server, but its answer was lost; the retry finds the same text at a newer version
    let tries = 0;
    const { saver, calls, conflicts, statuses } = setup(async (_b, c) => {
      tries++;
      if (tries === 1) throw new ApiError(0, "offline");
      throw new ChapterConflict(chapter(6, c.body));
    });
    saver.edit({ body: "written on the ferry" });
    await vi.advanceTimersByTimeAsync(AUTOSAVE_MS);
    await vi.advanceTimersByTimeAsync(RETRY_MS);
    expect(conflicts).toEqual([]);
    expect(calls.snapshots).toEqual([]);
    expect(statuses.at(-1)).toBe("saved");
    expect(saver.currentVersion).toBe(6);
  });

  it("leaving saves and keeps a snapshot only when something was written", async () => {
    const { saver, calls } = setup(async (_b, c) => chapter(2, c.body));
    await saver.leave();
    expect(calls.snapshots).toEqual([]);
    saver.edit({ body: "y" });
    await saver.leave();
    expect(calls.save).toHaveLength(1);
    expect(calls.snapshots).toEqual([["autosnap", {}]]);
  });
});
