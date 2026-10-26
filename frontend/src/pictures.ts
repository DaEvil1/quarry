// Pictures (docs/SPEC.md §17): uploaded into a world, placed in an entry's gallery or on a picture line in a text. A
// picture line is a line with an image link to a picture and nothing else, `![caption](picture:<id>)`; it is treated
// as a margin note is: not counted, not matched for names, left out of the compiled manuscript. The pattern is the
// server's (backend/src/quarry/margin.py).

import { ApiError, del, errorMessage, get, patch, put } from "./api";

export const PICTURE_LINE = /^[ \t]*!\[([^\]\n]*)\]\(picture:([0-9a-f-]{36})\)[ \t]*$/;
const PICTURE_LINES = /^[ \t]*!\[([^\]\n]*)\]\(picture:([0-9a-f-]{36})\)[ \t]*$/gm;

/** A line's picture, when it is a picture line. */
export function pictureLine(line: string): { caption: string; id: string } | null {
  const m = PICTURE_LINE.exec(line);
  return m ? { caption: m[1]!, id: m[2]! } : null;
}

/** The text with its picture lines blanked out, every other character where it was. */
export const blankPictures = (text: string) => (text.includes("](picture:") ? text.replace(PICTURE_LINES, (m) => " ".repeat(m.length)) : text);

/** The pictures a text's picture lines show, by id, in order, once each. */
export function pictureIds(text: string): string[] {
  if (!text.includes("](picture:")) return [];
  return [...new Set([...text.matchAll(PICTURE_LINES)].map((m) => m[2]!))];
}

/** A text cut into what is shown as text and what is shown as a picture (read-only places, docs/SPEC.md §17.3). */
export type Piece = { kind: "text"; text: string } | { kind: "picture"; id: string; caption: string };
export function pieces(text: string): Piece[] {
  const out: Piece[] = [];
  let buf: string[] = [];
  const flush = () => {
    if (buf.join("").trim()) out.push({ kind: "text", text: buf.join("\n").replace(/^\n+|\n+$/g, "") });
    buf = [];
  };
  for (const line of text.split("\n")) {
    const p = pictureLine(line);
    if (p) {
      flush();
      out.push({ kind: "picture", ...p });
    } else buf.push(line);
  }
  flush();
  return out;
}

/** What a text needs to draw a picture before it loads: its name and size. */
export interface PictureInfo {
  id: string;
  name: string;
  width: number;
  height: number;
}
export interface Picture extends PictureInfo {
  format: "jpeg" | "png" | "webp";
  size: number;
  created_at: string;
}
export interface PictureUses {
  entities: { id: string; name: string; kind: string }[];
  texts: { table: "chapter" | "journal" | "entity" | "cut"; id: string; title: string; state?: string; project?: string | null; date?: string; kind?: string }[];
  /** the captions it has where it is placed */
  captions: string[];
}
export interface GalleryPicture extends PictureInfo {
  caption: string;
}
/** Why a picture line can't show its picture. */
export type Missing = "deleted" | "elsewhere" | "offline";

export type FileKind = "full" | "view" | "thumb";
export const pictureUrl = (id: string, kind: FileKind) => `/api/pictures/${id}/${kind}`;

const base = (world: string) => `/api/worlds/${encodeURIComponent(world)}`;

export const NEEDS_NETWORK = "Pictures need the network";
export const TAKES = /^image\/(jpeg|png|webp)$/;

/** Send one file; the server makes the picture (docs/SPEC.md §17.4). */
export async function uploadPicture(world: string, file: File): Promise<Picture> {
  if (typeof navigator !== "undefined" && navigator.onLine === false) throw new ApiError(0, NEEDS_NETWORK);
  const form = new FormData();
  form.append("file", file, file.name || "picture");
  let res: Response;
  try {
    res = await fetch(`${base(world)}/pictures`, { method: "POST", credentials: "same-origin", body: form });
  } catch {
    throw new ApiError(0, NEEDS_NETWORK);
  }
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(res.status, data), data);
  return data as Picture;
}

export const listPictures = (world: string) =>
  get<{ pictures: (Picture & { uses: PictureUses })[]; count: number; bytes: number }>(`${base(world)}/pictures?uses=1`);
export const pictureIndex = (world: string) => get<PictureInfo[]>(`${base(world)}/pictures/index`);
export const whereabouts = (world: string, ids: string[]) =>
  get<Record<string, "deleted" | "elsewhere" | "here">>(`${base(world)}/pictures/whereabouts?ids=${ids.join(",")}`);
export const renamePicture = (id: string, name: string) => patch<Picture>(`/api/pictures/${id}`, { name });
export const deletePicture = (id: string) => del<void>(`/api/pictures/${id}`);
export const setGallery = (world: string, entity: string, pictures: { picture: string; caption: string }[]) =>
  put<GalleryPicture[]>(`${base(world)}/entities/${entity}/pictures`, pictures);

// why a picture line's picture isn't among the world's: asked once per picture, kept for the session
const reasons = new Map<string, Missing>();
const asked = new Set<string>();
export const missingReason = (id: string) => reasons.get(id);
/** Ask why these pictures (not among the world's) can't be shown; true when something new was learnt. */
export async function lookUp(world: string, ids: string[]): Promise<boolean> {
  const want = ids.filter((id) => !asked.has(id)).slice(0, 100);
  if (!want.length) return false;
  for (const id of want) asked.add(id);
  try {
    const found = await whereabouts(world, want);
    let learnt = false;
    for (const [id, where] of Object.entries(found)) {
      if (where !== "here") {
        reasons.set(id, where);
        learnt = true;
      }
    }
    return learnt;
  } catch {
    for (const id of want) asked.delete(id);
    return false;
  }
}
/** A picture now known again (uploaded, restored): no reason to miss it. */
export function forgetMissing(id: string) {
  reasons.delete(id);
  asked.delete(id);
}

/** "48 pictures · 61 MB" */
export function sizeText(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  return bytes ? `${Math.max(1, Math.round(bytes / 1024))} kB` : "0 kB";
}
export const countText = (n: number) => `${n} picture${n === 1 ? "" : "s"}`;

/** The files a drop or a paste carries that could be pictures (the server decides by opening them). */
export function imageFiles(data: DataTransfer | null): File[] {
  if (!data) return [];
  return [...data.files].filter((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|heic|gif|tiff?)$/i.test(f.name));
}
