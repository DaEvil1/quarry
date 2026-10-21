import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { readLastUsed, writeLastUsed } from "./lastUsed";
import { homeTarget } from "./router";
import { useSession } from "./stores/session";
import type { World } from "./types";

const world = (slug: string, projects: string[] = []): World => ({
  id: slug,
  name: slug.toUpperCase(),
  slug,
  role: "owner",
  projects: projects.map((p, i) => ({ id: `${slug}/${p}`, name: p, slug: p, kind: "novel", position: i })),
});

describe("homeTarget", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  function signedInWith(worlds: World[]) {
    useSession().me = { user: { id: "u", display_name: "Writer" }, worlds };
  }

  it("asks for a first world when there is none", () => {
    signedInWith([]);
    expect(homeTarget()).toEqual({ name: "new-world" });
  });

  it("opens the first world when nothing is remembered", () => {
    signedInWith([world("alpha"), world("beta")]);
    expect(homeTarget()).toEqual({ name: "world", params: { world: "alpha" } });
  });

  it("reopens the last world and project", () => {
    signedInWith([world("alpha"), world("beta", ["book"])]);
    writeLastUsed({ world: "beta", project: "book" });
    expect(homeTarget()).toEqual({ name: "project", params: { world: "beta", project: "book" } });
  });

  it("ignores a remembered world or project that is gone", () => {
    signedInWith([world("alpha", ["one"])]);
    writeLastUsed({ world: "alpha", project: "deleted" });
    expect(homeTarget()).toEqual({ name: "world", params: { world: "alpha" } });
    writeLastUsed({ world: "gone" });
    expect(homeTarget()).toEqual({ name: "world", params: { world: "alpha" } });
  });
});

describe("lastUsed", () => {
  it("survives storage that throws", () => {
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readLastUsed()).toEqual({});
    spy.mockRestore();
  });

  it("ignores junk", () => {
    localStorage.setItem("quarry.last", "{not json");
    expect(readLastUsed()).toEqual({});
    localStorage.setItem("quarry.last", JSON.stringify({ world: 3 }));
    expect(readLastUsed()).toEqual({ world: undefined, project: undefined });
  });
});

describe("homeTarget on a phone", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("opens capture in the last world", () => {
    useSession().me = { user: { id: "u", display_name: "W" }, worlds: [world("alpha"), world("beta", ["book"])] };
    writeLastUsed({ world: "beta", project: "book" });
    expect(homeTarget(true)).toEqual({ name: "capture", params: { world: "beta" } });
  });
});
