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
