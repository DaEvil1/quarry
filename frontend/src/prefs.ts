// Writing preferences, per device (a phone and a desk can differ). Kept in localStorage; if it is unavailable the
// defaults apply and nothing breaks.

import { defineStore } from "pinia";

import type { EntityKind } from "./types";

export interface WritingPrefs {
  /** colour names by kind in the editor and in texts */
  colourNames: boolean;
  /** kinds left uncoloured */
  plainKinds: EntityKind[];
  /** wavy underlines for likely misspellings while writing */
  underlines: boolean;
  /** how long the pointer rests on a name before its card shows (ms) */
  cardDelay: number;
  /** cards only while Ctrl (or Cmd) is held */
  cardsWithCtrl: boolean;
  /** after a keystroke, nothing opens for this long (ms) */
  quietMs: number;
  /** editor text size (px) and line width (characters) */
  textSize: number;
  lineWidth: number;
  focusMode: boolean;
  typewriter: boolean;
}

export const DEFAULT_PREFS: WritingPrefs = {
  colourNames: true,
  plainKinds: [],
  underlines: true,
  cardDelay: 450,
  cardsWithCtrl: false,
  quietMs: 1000,
  textSize: 18,
  lineWidth: 70,
  focusMode: false,
  typewriter: false,
};

const KEY = "quarry.prefs";

function read(): WritingPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<WritingPrefs>;
    return { ...DEFAULT_PREFS, ...raw };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export const usePrefs = defineStore("prefs", {
  state: (): WritingPrefs => read(),
  actions: {
    set<K extends keyof WritingPrefs>(key: K, value: WritingPrefs[K]) {
      this[key] = value as never;
      try {
        localStorage.setItem(KEY, JSON.stringify(this.$state));
      } catch {
        /* not kept, but applies for now */
      }
    },
    reset() {
      this.$patch({ ...DEFAULT_PREFS });
      try {
        localStorage.removeItem(KEY);
      } catch {
        /* nothing kept */
      }
    },
  },
});
