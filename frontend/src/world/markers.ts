// Loose-end markers in a text (docs/SPEC.md §14.3.2): TK, and "??": two or more question marks that don't follow a
// letter ("Varren's age ?? maybe 40", "(??)", a line that is just "???"), so a question in dialogue ("What??") is not
// one. Used by the editor's Loose ends and the Journal page's Loose ends tab.

export interface Marker {
  kind: "tk" | "??";
  from: number;
  to: number;
  /** the line it is on, trimmed */
  line: string;
}

const MARKERS = /\bTK\b|(?<!\p{L})\?{2,}/gu;

export function markers(text: string): Marker[] {
  const out: Marker[] = [];
  MARKERS.lastIndex = 0;
  for (let m = MARKERS.exec(text); m; m = MARKERS.exec(text)) {
    const start = text.lastIndexOf("\n", m.index - 1) + 1;
    const end = text.indexOf("\n", m.index);
    out.push({
      kind: m[0] === "TK" ? "tk" : "??",
      from: m.index,
      to: m.index + m[0].length,
      line: text.slice(start, end < 0 ? text.length : end).trim(),
    });
  }
  return out;
}
