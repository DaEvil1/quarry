// When a chapter is saved and when a snapshot (revision) is kept, as the spec sets it out:
//  - typing autosaves the working copy 1.5 s after the last keystroke, sending the version it started from;
//  - a snapshot is kept after 5 minutes without typing, after 30 minutes of continuous writing, on Ctrl+S (a
//    labelled checkpoint) and when the chapter is left;
//  - when another device saved first, this device's text is kept as a "conflict" revision and the newer text
//    is taken, so neither is lost;
//  - without a connection, saving is retried every 10 seconds and the text stays in the editor; a retry whose
//    text the server already has (the answer to the first try was lost) counts as saved, not as a conflict.

import { ApiError, unreachable } from "../api";
import { ChapterConflict, type Chapter } from "../manuscript";

export const AUTOSAVE_MS = 1500;
export const IDLE_MS = 5 * 60_000;
export const LONG_MS = 30 * 60_000;
export const RETRY_MS = 10_000;

export type SaveStatus = "saved" | "unsaved" | "saving" | "offline" | "conflict";

/** What can change in a chapter from the editor page; every save goes through the same queue. */
export interface Changes {
  title?: string;
  body?: string;
  pov_entity_id?: string | null;
}

export interface SaverDeps {
  save(baseVersion: number, changes: Changes): Promise<Chapter>;
  snapshot(reason: "autosnap" | "checkpoint" | "conflict", extra?: { label?: string; body?: string }): Promise<unknown>;
  now(): number;
}

export interface SaverHooks {
  saved(chapter: Chapter, sentBody: string | undefined): void;
  /** another device saved first: the editor should show `current`; `mine` was kept as a revision */
  conflict(current: Chapter, mine: string): void;
  status(status: SaveStatus): void;
}

export class ChapterSaver {
  private version: number;
  private pending: Changes = {};
  private inFlight: Promise<void> | null = null;
  private saveTimer: ReturnType<typeof setTimeout> | undefined;
  private idleTimer: ReturnType<typeof setTimeout> | undefined;
  private lastSnapshotAt: number;
  private editedSinceSnapshot = false;
  private closed = false;

  constructor(
    chapter: Pick<Chapter, "version">,
    private deps: SaverDeps,
    private hooks: SaverHooks,
  ) {
    this.version = chapter.version;
    this.lastSnapshotAt = deps.now();
  }

  /** The server version the editor's text builds on. */
  get currentVersion(): number {
    return this.version;
  }

  get dirty(): boolean {
    return Object.keys(this.pending).length > 0;
  }

  /** The text, title or point of view changed on the editor page. */
  edit(changes: Changes): void {
    if (this.closed) return;
    this.pending = { ...this.pending, ...changes };
    this.editedSinceSnapshot = true;
    this.hooks.status("unsaved");
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => void this.flush(), AUTOSAVE_MS);
    clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => void this.autosnap(), IDLE_MS);
  }

  /** Save now whatever is waiting. Resolves when the server has it (or saving failed and will be retried). */
  async flush(): Promise<void> {
    clearTimeout(this.saveTimer);
    if (this.inFlight) await this.inFlight;
    if (!this.dirty) return;
    const sending = this.pending;
    this.pending = {};
    this.hooks.status("saving");
    this.inFlight = (async () => {
      try {
        const ch = await this.deps.save(this.version, sending);
        this.version = ch.version;
        this.hooks.saved(ch, sending.body);
        this.hooks.status(this.dirty ? "unsaved" : "saved");
        if (this.deps.now() - this.lastSnapshotAt >= LONG_MS) await this.keep("autosnap");
      } catch (e) {
        const sameText = e instanceof ChapterConflict &&
          (sending.body === undefined || sending.body === e.current.body) &&
          (sending.title === undefined || sending.title === e.current.title) &&
          (sending.pov_entity_id === undefined || sending.pov_entity_id === (e.current.pov?.id ?? null));
        if (sameText) {
          // the earlier try did reach the server; only its answer was lost (signal dropped mid-save)
          const current = (e as ChapterConflict).current;
          this.version = current.version;
          this.hooks.saved(current, sending.body);
          this.hooks.status(this.dirty ? "unsaved" : "saved");
        } else if (e instanceof ChapterConflict) {
          const mine = sending.body ?? e.current.body;
          // keep this device's text before taking the other one
          if (sending.body !== undefined && sending.body !== e.current.body) {
            await this.deps.snapshot("conflict", { body: sending.body }).catch(() => undefined);
          }
          this.version = e.current.version;
          this.pending = {};
          this.hooks.conflict(e.current, mine);
          this.hooks.status("conflict");
        } else {
          // keep the text for the next try; anything typed meanwhile wins over what was being sent
          this.pending = { ...sending, ...this.pending };
          this.hooks.status(e instanceof ApiError && !unreachable(e) && e.status < 500 ? "unsaved" : "offline");
          clearTimeout(this.saveTimer);
          if (!this.closed) this.saveTimer = setTimeout(() => void this.flush(), RETRY_MS);
        }
      }
    })();
    try {
      await this.inFlight;
    } finally {
      this.inFlight = null;
    }
    if (this.dirty && !this.closed) {
      clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => void this.flush(), AUTOSAVE_MS);
    }
  }

  /** Ctrl+S: save, then keep a checkpoint with an optional label. */
  async checkpoint(label?: string): Promise<void> {
    await this.flush();
    await this.keep("checkpoint", label);
  }

  /** Leaving the chapter (closing, switching away, backgrounding): save and keep a snapshot. */
  async leave(): Promise<void> {
    await this.flush();
    if (this.editedSinceSnapshot) await this.keep("autosnap");
  }

  /** The editor took a new text from elsewhere (a restore, another device): carry on from its version. */
  rebase(chapter: Pick<Chapter, "version">): void {
    this.version = chapter.version;
    this.pending = {};
    clearTimeout(this.saveTimer);
    this.hooks.status("saved");
  }

  close(): void {
    this.closed = true;
    clearTimeout(this.saveTimer);
    clearTimeout(this.idleTimer);
  }

  private async autosnap(): Promise<void> {
    await this.flush();
    if (this.editedSinceSnapshot) await this.keep("autosnap");
  }

  private async keep(reason: "autosnap" | "checkpoint", label?: string): Promise<void> {
    try {
      await this.deps.snapshot(reason, label ? { label } : {});
      this.lastSnapshotAt = this.deps.now();
      this.editedSinceSnapshot = false;
    } catch {
      /* the text itself is saved; a missed snapshot is retried at the next occasion */
    }
  }
}
