import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { find, hint, perform } from "./guide/engine";
import { TOURS } from "./guide/tours";
import { readLastUsed, writeLastUsed } from "./lastUsed";
import { forgetSandbox } from "./stores/guide";

// jsdom lays nothing out: an element counts as shown unless it (or a parent) is marked hidden
beforeEach(() => {
  vi.spyOn(Element.prototype, "getClientRects").mockImplementation(function (this: Element) {
    return (this.closest("[hidden]") ? [] : [{}]) as unknown as DOMRectList;
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
  localStorage.clear();
});

const stopped = () => false;

describe("the Guide's steps (docs/SPEC.md §15.3)", () => {
  it("finds an element by selector and text, skipping hidden ones, and the nth", () => {
    document.body.innerHTML = `
      <ul><li class="row">The Crossing</li><li class="row" hidden>What the River Kept (hidden)</li>
      <li class="row">What the River Kept</li><li class="row">The Locks</li></ul>`;
    expect(find(document, { css: ".row", text: "River Kept" })?.textContent).toBe("What the River Kept");
    expect(find(document, { css: ".row", nth: 2 })?.textContent).toBe("The Locks");
    expect(find(document, { css: ".row", text: "Ash Season" })).toBeNull();
  });

  it("chooses an option by its value or by the words it shows, and says when there is none", async () => {
    document.body.innerHTML = `<select><option value="">every era</option><option value="e-17">The Ash Summers</option></select>`;
    const sel = document.querySelector("select")!;
    const changed = vi.fn();
    sel.addEventListener("change", changed);
    await perform(sel, { choose: "The Ash Summers" }, { slow: false, stopped });
    expect(sel.value).toBe("e-17");
    await perform(sel, { choose: "" }, { slow: false, stopped });
    expect(sel.value).toBe("");
    expect(changed).toHaveBeenCalledTimes(2);
    await expect(perform(sel, { choose: "The Lock Years" }, { slow: false, stopped })).rejects.toThrow("The Lock Years");
  });

  it("types into a field so v-model hears it, a letter at a time when watched", async () => {
    document.body.innerHTML = `<input aria-label="Event" />`;
    const box = document.querySelector("input")!;
    const seen: string[] = [];
    box.addEventListener("input", () => seen.push(box.value));
    await perform(box, { fill: "392" }, { slow: true, speed: 100, stopped });
    expect(seen).toEqual(["", "3", "39", "392"]);
    await perform(box, { fill: "The Founding" }, { slow: false, stopped });
    expect(box.value).toBe("The Founding");
  });

  it("presses keys with their modifiers on the element", async () => {
    document.body.innerHTML = `<div class="cm-content"></div>`;
    const el = document.querySelector("div")!;
    const keys: string[] = [];
    window.addEventListener("keydown", (e) => keys.push(`${e.ctrlKey ? "Ctrl+" : ""}${e.shiftKey ? "Shift+" : ""}${e.key} ${e.keyCode}`));
    await perform(el, { key: "x", ctrl: true, shift: true }, { slow: false, stopped });
    await perform(el, { key: "Enter" }, { slow: false, stopped });
    // a shifted letter comes as a capital with its key code, as a keyboard sends it (CodeMirror needs both)
    expect(keys).toEqual(["Ctrl+Shift+X 88", "Enter 13"]);
  });

  it("says what to do when it's the writer's turn", () => {
    expect(hint({ click: true, shift: true })).toBe("Shift-click the highlighted button.");
    expect(hint({ key: "s", ctrl: true })).toBe("Press Ctrl+s.");
    expect(hint({ fill: "Cade tells it" })).toBe("Type “Cade tells it”.");
    expect(hint(undefined)).toBe("");
  });
});

describe("the sandbox on the device (docs/SPEC.md §15.2)", () => {
  it("takes out what the sandbox left, and never leaves Quarry to reopen in it", () => {
    localStorage.setItem("timeline:guide-sandbox", "{}");
    localStorage.setItem("timeline:the-grey-coast", "{}");
    localStorage.setItem("quarry.capture", JSON.stringify({ "guide-sandbox": { kind: "spark" }, "the-grey-coast": { kind: "task" } }));
    localStorage.setItem("quarry.guide", JSON.stringify({ capture: "2026-10-25" }));
    writeLastUsed({ world: "guide-sandbox" });
    forgetSandbox("guide-sandbox");
    expect(localStorage.getItem("timeline:guide-sandbox")).toBeNull();
    expect(localStorage.getItem("timeline:the-grey-coast")).toBe("{}");
    expect(JSON.parse(localStorage.getItem("quarry.capture")!)).toEqual({ "the-grey-coast": { kind: "task" } });
    expect(localStorage.getItem("quarry.guide")).not.toBeNull();
    expect(readLastUsed()).toEqual({});
  });
});

describe("the walkthroughs (docs/SPEC.md §15.6)", () => {
  it("have their own ids, and every step that does something says where", () => {
    expect(new Set(TOURS.map((t) => t.id)).size).toBe(TOURS.length);
    for (const t of TOURS) {
      expect(t.steps.length, t.id).toBeGreaterThan(3);
      for (const [i, s] of t.steps.entries()) {
        expect(s.say.trim(), `${t.id} ${i + 1}`).not.toBe("");
        if (s.act) expect(s.target, `${t.id} ${i + 1}`).toBeTruthy();
        if (s.in === "phone") expect(t.steps.slice(0, i + 1).some((x) => typeof x.phone === "string"), `${t.id} ${i + 1}`).toBe(true);
      }
    }
  });
});
