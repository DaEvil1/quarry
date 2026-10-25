// Shared by the walkthroughs: the demo's first book, and a data-testid selector.

/** The Ferryman's Daughter, the demo world's first book, in the sandbox (`{w}` is the sandbox's address). */
export const BOOK = "/w/{w}/p/the-ferrymans-daughter";
/** Ash Season, the demo's second book. */
export const BOOK_TWO = "/w/{w}/p/ash-season";

export const tid = (id: string) => `[data-testid="${id}"]`;
