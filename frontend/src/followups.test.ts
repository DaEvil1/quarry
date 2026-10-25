// Phase 14 in the browser (docs/SPEC.md §16): the pill worked out from the counts, the follow-up list's words, the
// order "Follows a decision…" offers decisions in, and the follow-up step's keyboard.

import "fake-indexeddb/auto";

import { flushPromises, mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("vue-router", () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ replace: vi.fn() }), RouterLink: { template: "<a><slot /></a>" } }));

import FollowUpStep from "./components/FollowUpStep.vue";
import { decisionDay, followersText, followOrder, followupTail, pillText, type Followup } from "./followups";

const fu = (over: Partial<Followup>): Followup => ({
  id: "f", state: "todo", what: "", dropped_on: null, kind: "fact", text: "", standing: "planned", status: null,
  closed_at: null, link: null, written: null, ...over,
});

describe("the pill", () => {
  it("is nothing for a settled decision, n of m to do, then done", () => {
    expect(pillText(null)).toBeNull();
    expect(pillText(undefined)).toBeNull();
    expect(pillText({ todo: 0, done: 0, dropped: 0 })).toBeNull();
    expect(pillText({ todo: 1, done: 0, dropped: 0 })).toBe("1 of 1 to do");
    expect(pillText({ todo: 1, done: 1, dropped: 0 })).toBe("1 of 2 to do");
    expect(pillText({ todo: 0, done: 1, dropped: 0 })).toBe("done");
    // a task rejected counts toward done (listed as dropped)
    expect(pillText({ todo: 0, done: 1, dropped: 1 })).toBe("done");
  });
});

describe("the follow-up list", () => {
  it("says what each line is and when", () => {
    expect(followupTail(fu({}))).toBe("planned");
    expect(followupTail(fu({ kind: "task", state: "done", status: "accepted", closed_at: "2026-10-20T09:00:00Z" }))).toBe("task · accepted 20 Oct");
    expect(followupTail(fu({ kind: "task", state: "todo", status: "deferred" }))).toBe("task · deferred");
    expect(followupTail(fu({ kind: null, state: "dropped", dropped_on: "2026-10-22" }))).toBe("22 Oct · the row was deleted");
    expect(followupTail(fu({ kind: null, state: "dropped" }))).toBe("the row was deleted");
    expect(followupTail(fu({ state: "dropped", dropped_on: "2026-10-22" }))).toBe("planned · dropped 22 Oct");
    expect(decisionDay("2026-10-12")).toBe("12 Oct 2026");
  });

  it("warns before a decision with follow-ups goes", () => {
    expect(followersText([fu({ kind: "fact" }), fu({ kind: "task" })])).toBe("1 planned fact and 1 task follow this decision. They stay, without the decision.");
    expect(followersText([fu({ kind: "relationship" })])).toBe("1 planned relationship follows this decision. It stays, without the decision.");
    expect(followersText([fu({ kind: null })])).toBe("");
  });

  it("offers the decisions tagged with the row's entries first, newest first", () => {
    const d = (id: string, day: string, tags: string[]) => ({ id, decided_on: day, entities: tags.map((t) => ({ id: t })) });
    const list = [d("a", "2026-10-01", []), d("b", "2026-10-05", ["v"]), d("c", "2026-10-09", []), d("e", "2026-10-02", ["v"])];
    expect(followOrder(list, ["v"]).map((x) => x.id)).toEqual(["b", "e", "c", "a"]);
  });
});

describe("the follow-up step", () => {
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  const offers = {
    chapters: [{ id: "c9", title: "The Drowned Bell", n: 9, project: "salt", project_name: "The Salt Road", label: "chapter 9, The Drowned Bell" }],
    entities: [{ id: "v", name: "Varren", kind: "character", tagged: true }, { id: "i", name: "Isolde", kind: "character", tagged: true }],
  };
  afterEach(() => vi.unstubAllGlobals());

  async function step() {
    const sent: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      sent.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
      if (url.endsWith("/offers")) return Promise.resolve(json(offers));
      if (url.endsWith("/fact-suggestions")) return Promise.resolve(json({}));
      if (url.endsWith("/followups")) return Promise.resolve(json({ followup: fu({ id: "new" }), made: { table: "fact", id: "x" }, counts: { todo: 1, done: 0, dropped: 0 } }));
      return Promise.resolve(json([]));
    }));
    const w = mount(FollowUpStep, { props: { world: "delta", decision: { id: "d", text: "Varren dies at the end of chapter 9" }, lead: "Decision logged", autofocus: true }, global: { plugins: [createPinia()], stubs: { RouterLink: true } }, attachTo: document.body });
    await flushPromises();
    return { w, sent };
  }
  const key = async (w: Awaited<ReturnType<typeof step>>["w"], k: string, at = w.find('[data-testid="followup-step"]')) => {
    await at.trigger("keydown", { key: k });
    await flushPromises();
  };

  it("opens a form on f, w and t, the picker on x, and Esc goes back to the row", async () => {
    const { w } = await step();
    expect(w.text()).toContain("Decision logged");
    for (const [k, form] of [["f", "fu-fact-form"], ["w", "fu-relationship-form"], ["t", "fu-task-form"], ["x", "fu-attach-form"]]) {
      await key(w, k!);
      expect(w.find(`[data-testid="${form}"]`).exists()).toBe(true);
      await key(w, "Escape");
      expect(w.find('[data-testid="followup-row"]').exists()).toBe(true);
    }
    expect(w.emitted("done")).toBeUndefined();
    w.unmount();
  });

  it("Enter on the row ends the step, and so does Esc", async () => {
    const { w } = await step();
    await key(w, "Enter");
    expect(w.emitted("done")).toHaveLength(1);
    await key(w, "Escape");
    expect(w.emitted("done")).toHaveLength(2);
    w.unmount();
  });

  it("offers the chapter the decision names, used only after a click, and comes back as + another", async () => {
    const { w, sent } = await step();
    await key(w, "f");
    expect(w.find('[data-testid="fu-offer"]').text()).toContain("Named in the decision: chapter 9, The Drowned Bell");
    // the first tagged entry is chosen
    expect(w.find('[aria-pressed="true"]').text()).toBe("Varren");
    await w.find('input[aria-label="Follow-up fact label"]').setValue("status");
    await w.find('input[aria-label="Follow-up fact value"]').setValue("dead");
    const fromChapter = () => (sent.at(-1)!.body as { fact: { from_chapter_id: string | null } }).fact.from_chapter_id;
    await w.find('[data-testid="fu-fact-form"]').trigger("submit");
    await flushPromises();
    expect(fromChapter()).toBeNull();
    expect(w.text()).toContain("+ another");
    await key(w, "f");
    await w.find('input[aria-label="Follow-up fact label"]').setValue("status");
    await w.findAll('[data-testid="fu-offer"] button')[0]!.trigger("click");
    await w.find('[data-testid="fu-fact-form"]').trigger("submit");
    await flushPromises();
    expect(fromChapter()).toBe("c9");
    expect(sent.at(-1)!.body).toMatchObject({ fact: { entity_id: "v", label: "status", standing: "planned" } });
    w.unmount();
  });

  it("ticks the decision's entries in a task and offers its chapter unticked", async () => {
    const { w, sent } = await step();
    await key(w, "t");
    const chapter = w.find('[data-testid="fu-task-chapter"]');
    expect(chapter.attributes("aria-pressed")).toBe("false");
    await w.find('input[aria-label="Follow-up task"]').setValue("Plant the bell's crack");
    await chapter.trigger("click");
    await w.find('[data-testid="fu-task-form"]').trigger("submit");
    await flushPromises();
    expect(sent.at(-1)!.body).toEqual({ item: { body: "Plant the bell's crack", entities: ["v", "i"], chapters: ["c9"] } });
    w.unmount();
  });
});
