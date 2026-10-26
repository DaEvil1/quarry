// The full view of a picture (docs/SPEC.md §17.2): opened from a gallery, a main picture or a picture line, with ‹ ›
// through the pictures it was opened among. One for the whole app, drawn by the shell.

import { defineStore } from "pinia";

export interface Shown {
  id: string;
  name: string;
  caption: string;
}

export const useViewer = defineStore("viewer", {
  state: () => ({ items: [] as Shown[], index: 0, open: false }),
  getters: {
    current: (s): Shown | null => (s.open ? (s.items[s.index] ?? null) : null),
  },
  actions: {
    show(items: Shown[], index = 0) {
      if (!items.length) return;
      this.items = items;
      this.index = Math.max(0, Math.min(index, items.length - 1));
      this.open = true;
    },
    step(by: number) {
      if (this.items.length < 2) return;
      this.index = (this.index + by + this.items.length) % this.items.length;
    },
    close() {
      this.open = false;
    },
  },
});
