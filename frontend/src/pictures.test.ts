import { describe, expect, it } from "vitest";

import { blankPictures, pictureIds, pictureLine, pieces, sizeText } from "./pictures";
import { countWords, storyText } from "./words";

const ID = "3f2a9c1e-8b4d-4c1a-9e57-2d6f0b8a41c3";

describe("picture lines (docs/SPEC.md §17.3)", () => {
  it("is a line with an image link to a picture and nothing else", () => {
    expect(pictureLine(`![The harbour at dusk](picture:${ID})`)).toEqual({ caption: "The harbour at dusk", id: ID });
    expect(pictureLine(`  ![](picture:${ID})  `)).toEqual({ caption: "", id: ID });
    expect(pictureLine(`Isolde ![x](picture:${ID}) waits`)).toBeNull();
    expect(pictureLine("![web](https://example.com/x.png)")).toBeNull();
    expect(pictureLine(`%% ![x](picture:${ID})`)).toBeNull();
  });

  it("is not counted, whatever its caption says, and keeps every other character where it was", () => {
    const text = `Isolde waits.\n![Isolde at the harbour, waving](picture:${ID})\nThe bell rang.`;
    expect(countWords(storyText(text))).toBe(5);
    expect(blankPictures(text)).toHaveLength(text.length);
    expect(pictureIds(`${text}\n![again](picture:${ID})`)).toEqual([ID]);
  });

  it("cuts a text into prose and pictures for read-only pages", () => {
    expect(pieces(`A town.\n\n![The gate](picture:${ID})\n\nIts bell is old.`)).toEqual([
      { kind: "text", text: "A town." },
      { kind: "picture", id: ID, caption: "The gate" },
      { kind: "text", text: "Its bell is old." },
    ]);
  });

  it("says sizes as the Pictures page does", () => {
    expect(sizeText(0)).toBe("0 kB");
    expect(sizeText(30_000)).toBe("29 kB");
    expect(sizeText(64 * 1024 * 1024)).toBe("64 MB");
  });
});

describe("Restore's result (docs/SPEC.md §17.6)", () => {
  it("says how many pictures came, and what was skipped", async () => {
    const { restoredText } = await import("./manuscript");
    const w = { id: "w", name: "W", slug: "w", role: "owner", projects: [] };
    expect(restoredText({ ...w, pictures: 48, skipped: [] })).toBe("Restored, with 48 pictures");
    expect(restoredText({ ...w, pictures: 1, skipped: ["Pictures/notes.txt"] })).toBe("Restored, with 1 picture. Skipped: Pictures/notes.txt");
    expect(restoredText({ ...w })).toBe("Restored");
  });
});
