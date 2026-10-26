// What the chapter and journal editors need for picture lines (docs/SPEC.md §17.3): each picture's size from the
// world's cards, why one can't be shown, the full view, and uploading a pasted or dropped picture.

import { forgetMissing, lookUp, missingReason, uploadPicture } from "../pictures";
import { useViewer } from "../stores/viewer";
import { useCards } from "../world/cards";
import type { PictureHooks } from "./pictures";

export function editorPictureHooks(world: () => string, status: (text: string | null, error?: boolean) => void, redraw: () => void): PictureHooks {
  const cards = useCards();
  const viewer = useViewer();
  return {
    info: (id) => cards.pictureById.get(id),
    missing(id) {
      const why = missingReason(id);
      if (why) return why;
      // not among the world's pictures once its cards are here: ask why, once, and draw the line again
      if (cards.cards.length && !cards.pictureById.has(id)) void lookUp(world(), [id]).then((learnt) => learnt && redraw());
      return undefined;
    },
    open: (id, caption) => viewer.show([{ id, caption, name: cards.pictureById.get(id)?.name ?? "" }]),
    async upload(file) {
      const p = await uploadPicture(world(), file);
      cards.putPicture(p);
      forgetMissing(p.id);
      return p;
    },
    status,
  };
}
