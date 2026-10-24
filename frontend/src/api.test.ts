import { describe, expect, it } from "vitest";

import { ApiError, errorMessage, unreachable } from "./api";

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
    expect(errorMessage(500, null)).toMatch(/on the server/);
    expect(errorMessage(502, "<html>")).toMatch(/may be restarting/);
    expect(errorMessage(418, null)).toBe("Request failed (418).");
  });
});

describe("unreachable", () => {
  it("is no network, or nginx answering for an app that is restarting", () => {
    for (const status of [0, 502, 503, 504]) expect(unreachable(new ApiError(status, ""))).toBe(true);
    for (const status of [401, 404, 409, 500]) expect(unreachable(new ApiError(status, ""))).toBe(false);
    expect(unreachable(new Error("other"))).toBe(false);
  });
});
