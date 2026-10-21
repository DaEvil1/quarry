export type ProjectKind = "novel" | "novella" | "short" | "other";

export const PROJECT_KINDS: { value: ProjectKind; label: string }[] = [
  { value: "novel", label: "Novel" },
  { value: "novella", label: "Novella" },
  { value: "short", label: "Short story" },
  { value: "other", label: "Other" },
];

export interface Project {
  id: string;
  name: string;
  slug: string;
  kind: ProjectKind;
  position: number;
}

export interface World {
  id: string;
  name: string;
  slug: string;
  role: string;
  projects: Project[];
}

export interface User {
  id: string;
  display_name: string;
}

export interface Me {
  user: User;
  worlds: World[];
}

export interface PasskeyInfo {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
}

/** What the backend sends to start a WebAuthn ceremony. */
export interface Ceremony<T> {
  challenge_id: string;
  options: T;
}

export function kindLabel(kind: ProjectKind): string {
  return PROJECT_KINDS.find((k) => k.value === kind)?.label ?? kind;
}
