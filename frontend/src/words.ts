// Counting words the way the server does: letters and digits, with inner apostrophes and hyphens.
import { blankPictures } from "./pictures";

const WORD_RE = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;

export const countWords = (text: string) => text.match(WORD_RE)?.length ?? 0;

const MARGIN = /^[ \t]*%%[^\n]*/gm;
/** The chapter without its margin notes (%% lines) and picture lines (docs/SPEC.md §17.3), every other character
 * where it was. */
export const storyText = (text: string) => blankPictures(text.replace(MARGIN, (m) => " ".repeat(m.length)));
