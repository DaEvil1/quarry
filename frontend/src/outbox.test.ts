import "fake-indexeddb/auto";

import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { localDb, readMeSnapshot, saveMeSnapshot } from "./localdb";
import { useOutbox } from "./stores/outbox";
import { useSession } from "./stores/session";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function server(handler: Handler) {
  vi.stubGlobal("fetch", vi.fn((url: string, init: RequestInit) => Promise.resolve(handler(url, init))));
}
const offline = () => vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const capture = { world: "coast", body: "an idea", kind: "spark" as const, project: null, source: "phone" };

beforeEach(async () => {
  setActivePinia(createPinia());
  await localDb.outbox.clear();
  await localDb.kv.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("outbox", () => {
  it("sends a capture straight away when online", async () => {
    const bodies: unknown[] = [];
    server((url, init) => {
      bodies.push({ url, ...JSON.parse(String(init.body)) });
      return json(201, {});
    });
    const outbox = useOutbox();
    expect(await outbox.add(capture)).toBe(true);
    expect(outbox.pending).toEqual([]);
    expect(bodies).toEqual([
      expect.objectContaining({ url: "/api/worlds/coast/items", body: "an idea", kind: "spark", source: "phone" }),
    ]);
  });

  it("keeps captures while offline and sends them, in order and with their ids, later", async () => {
    offline();
    const outbox = useOutbox();
    expect(await outbox.add({ ...capture, body: "first", capturedAt: "2026-10-21T08:00:00Z" })).toBe(false);
    expect(await outbox.add({ ...capture, body: "second", capturedAt: "2026-10-21T08:05:00Z" })).toBe(false);
    expect(outbox.waiting).toBe(2);
    expect(outbox.online).toBe(false);

    const sent: { id: string; body: string; captured_at: string }[] = [];
    server((_url, init) => {
      sent.push(JSON.parse(String(init.body)));
      return json(201, {});
    });
    await outbox.send();
    expect(sent.map((s) => [s.body, s.captured_at])).toEqual([
      ["first", "2026-10-21T08:00:00Z"],
      ["second", "2026-10-21T08:05:00Z"],
    ]);
    expect(sent.every((s) => /^[0-9a-f-]{36}$/.test(s.id))).toBe(true);
    expect(outbox.waiting).toBe(0);
    expect(outbox.online).toBe(true);
  });

  it("keeps a refused capture, marked, and goes on with the rest", async () => {
    offline();
    const outbox = useOutbox();
    await outbox.add({ ...capture, body: "bad project", project: "gone", capturedAt: "2026-10-21T08:00:00Z" });
    await outbox.add({ ...capture, body: "fine", capturedAt: "2026-10-21T08:01:00Z" });
    server((_url, init) =>
      JSON.parse(String(init.body)).project === "gone"
        ? json(422, { detail: "No such project in this world." })
        : json(201, {}),
    );
    await outbox.send();
    expect(outbox.pending.map((p) => [p.body, p.error])).toEqual([["bad project", "No such project in this world."]]);
    expect(outbox.waiting).toBe(0);

    await outbox.retry(outbox.pending[0].id, { project: null });
    expect(outbox.pending).toEqual([]);
  });

  it("stops and asks for sign-in on 401, keeping everything", async () => {
    server(() => json(401, { detail: "Sign in to continue." }));
    const outbox = useOutbox();
    expect(await outbox.add(capture)).toBe(false);
    expect(outbox.needsSignIn).toBe(true);
    expect(outbox.waiting).toBe(1);
  });
});

describe("session offline", () => {
  const me = { user: { id: "u", display_name: "Writer" }, worlds: [] };

  it("opens from the copy on this device when the server can't be reached", async () => {
    await saveMeSnapshot(me);
    offline();
    const session = useSession();
    expect(await session.load()).toBe(true);
    expect(session.offline).toBe(true);
    expect(session.me).toEqual(me);
  });

  it("also opens from the copy while the server is restarting, instead of asking to sign in", async () => {
    await saveMeSnapshot(me);
    server(() => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const session = useSession();
    expect(await session.load()).toBe(true);
    expect(session.offline).toBe(true);
    expect(await readMeSnapshot()).toEqual(me);
  });

  it("keeps captures waiting while the server is restarting", async () => {
    server(() => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const outbox = useOutbox();
    expect(await outbox.add(capture)).toBe(false);
    expect(outbox.waiting).toBe(1);
  });

  it("refreshes the copy when online and drops it when signed out", async () => {
    server(() => json(200, me));
    const session = useSession();
    expect(await session.load()).toBe(true);
    expect(await readMeSnapshot()).toEqual(me);
    server(() => json(401, { detail: "Sign in to continue." }));
    expect(await session.load()).toBe(false);
    expect(await readMeSnapshot()).toBeNull();
  });

  it("without a copy, offline is an error", async () => {
    offline();
    await expect(useSession().load()).rejects.toThrow(/could not reach/);
  });
});
