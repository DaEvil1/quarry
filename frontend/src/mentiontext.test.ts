import { RouterLinkStub, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("./bible", () => ({
  fixes: {
    replace: vi.fn(() => Promise.resolve({ replaced: 1 })),
    addSpelling: vi.fn(() => Promise.resolve()),
    notATypo: vi.fn(() => Promise.resolve()),
  },
}));

import { fixes } from "./bible";
import MentionText from "./components/MentionText.vue";
import type { Mention } from "./types";

const m = (start: number, end: number, kind: Mention["kind"], name = "Varren"): Mention => ({
  entity_id: "e1",
  entity_name: name,
  start,
  end,
  matched_text: "Varen",
  kind,
});

function render(text: string, mentions: Mention[]) {
  return mount(MentionText, {
    props: { text, mentions, world: "coast", source: { table: "item", id: "i1" } },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("MentionText", () => {
  it("keeps the text and links names", () => {
    const w = render("Varren meets Varen.", [m(0, 6, "exact"), m(13, 18, "near_miss")]);
    expect(w.text()).toBe("Varren meets Varen.");
    expect(w.findComponent(RouterLinkStub).props("to")).toEqual({ name: "entity", params: { world: "coast", id: "e1" } });
    expect(w.find("button.near-miss").text()).toBe("Varen");
  });

  it("ignores overlapping or out-of-range mentions instead of garbling the text", () => {
    const w = render("Short", [m(0, 5, "exact"), m(2, 4, "alias"), m(3, 99, "exact")]);
    expect(w.text()).toBe("Short");
  });

  it("offers the three fixes for a near miss and reports when one is done", async () => {
    const w = render("Varen sails.", [m(0, 5, "near_miss")]);
    await w.find("button.near-miss").trigger("click");
    const items = w.findAll("[role=menuitem]");
    expect(items.map((b) => b.text())).toEqual(["Replace with Varren", "“Varen” is another spelling", "Not a typo"]);

    await items[0].trigger("click");
    await vi.waitFor(() => expect(w.emitted("fixed")).toHaveLength(1));
    expect(fixes.replace).toHaveBeenCalledWith("coast", "Varen", "e1", { table: "item", id: "i1" });
    expect(w.find("[role=menu]").exists()).toBe(false);
  });
});
