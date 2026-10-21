import { describe, expect, it } from "vitest";

import { errorMessage } from "./api";

describe("errorMessage", () => {
  it("uses the server's sentence", () => {
    expect(errorMessage(409, { detail: "Another world already uses that address." })).toBe(
      "Another world already uses that address.",
    );
  });

  it("names the field of a validation error", () => {
    const body = { detail: [{ loc: ["body", "name"], msg: "String should have at least 1 character" }] };
    expect(errorMessage(422, body)).toBe("Check name: String should have at least 1 character");
  });

  it("explains network and server failures", () => {
    expect(errorMessage(0, null)).toMatch(/could not reach/);
    expect(errorMessage(502, "<html>")).toMatch(/on the server/);
    expect(errorMessage(418, null)).toBe("Request failed (418).");
  });
});
