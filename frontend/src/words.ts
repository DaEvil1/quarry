// Counting words the way the server does: letters and digits, with inner apostrophes and hyphens.
const WORD_RE = /[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu;

export const countWords = (text: string) => text.match(WORD_RE)?.length ?? 0;
