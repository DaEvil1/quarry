// Remembers the last world and project opened on this device, so Quarry reopens where you left off.
// Browser storage can be missing or blocked (private windows); everything here degrades to "nothing remembered".

const KEY = "quarry.last";

export interface LastUsed {
  world?: string;
  project?: string;
}

export function readLastUsed(): LastUsed {
  try {
    const raw = localStorage.getItem(KEY);
    const v: unknown = raw ? JSON.parse(raw) : {};
    if (v && typeof v === "object") {
      const { world, project } = v as Record<string, unknown>;
      return {
        world: typeof world === "string" ? world : undefined,
        project: typeof project === "string" ? project : undefined,
      };
    }
  } catch {
    /* storage unavailable or corrupt */
  }
  return {};
}

export function writeLastUsed(value: LastUsed): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
}

// The project and kind last picked on the capture screen, per world, so the next capture starts there.
const CAPTURE_KEY = "quarry.capture";

export interface CaptureDefaults {
  project: string | null;
  kind: "spark" | "question" | "task";
}

export function readCaptureDefaults(world: string): CaptureDefaults | null {
  try {
    const all = JSON.parse(localStorage.getItem(CAPTURE_KEY) ?? "{}") as Record<string, unknown>;
    const v = all[world] as Partial<CaptureDefaults> | undefined;
    if (!v || typeof v !== "object") return null;
    const kind = v.kind === "question" || v.kind === "task" ? v.kind : "spark";
    return { project: typeof v.project === "string" ? v.project : null, kind };
  } catch {
    return null;
  }
}

export function writeCaptureDefaults(world: string, value: CaptureDefaults): void {
  try {
    const all = JSON.parse(localStorage.getItem(CAPTURE_KEY) ?? "{}") as Record<string, unknown>;
    all[world] = value;
    localStorage.setItem(CAPTURE_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable */
  }
}

/** Phone-sized screen: capture comes first there. */
export function isPhone(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(max-width: 767px)").matches;
}
