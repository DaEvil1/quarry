import { describe, expect, it } from "vitest";

import { sharedText } from "./share";

describe("sharedText", () => {
  it("joins title, text and link", () => {
    expect(sharedText({ title: "A page", text: "a quote", url: "https://example.com/x" })).toBe(
      "A page\n\na quote\n\nhttps://example.com/x",
    );
  });

  it("does not repeat a link already in the text, or a title the text starts with", () => {
    expect(sharedText({ title: "A page", text: "A page https://example.com/x", url: "https://example.com/x" })).toBe(
      "A page https://example.com/x",
    );
  });

  it("copes with missing parts", () => {
    expect(sharedText({ url: " https://example.com " })).toBe("https://example.com");
    expect(sharedText({})).toBe("");
  });
});
