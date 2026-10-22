// A name's card over ordinary pages (items, journal, decisions): the same card the editor shows, after the same
// pause, staying open while the pointer moves onto it.

import { cardDom } from "../editor/strips";
import type { Card } from "./cards";

let shown: HTMLElement | null = null;
let openTimer = 0;
let closeTimer = 0;

export function hideCard(now = false) {
  window.clearTimeout(openTimer);
  window.clearTimeout(closeTimer);
  const close = () => {
    shown?.remove();
    shown = null;
  };
  if (now) close();
  else closeTimer = window.setTimeout(close, 200);
}

export function showCard(anchor: HTMLElement, card: Card | undefined, open: () => void, delay: number) {
  window.clearTimeout(openTimer);
  window.clearTimeout(closeTimer);
  openTimer = window.setTimeout(() => {
    if (!anchor.isConnected) return;
    shown?.remove();
    const dom = cardDom(card, {
      open: () => {
        hideCard(true);
        open();
      },
    });
    dom.classList.add("qcard-floating");
    dom.addEventListener("mouseenter", () => window.clearTimeout(closeTimer));
    dom.addEventListener("mouseleave", () => hideCard());
    document.body.append(dom);
    const r = anchor.getBoundingClientRect();
    const w = dom.offsetWidth;
    const h = dom.offsetHeight;
    const left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    const below = r.bottom + 6 + h < window.innerHeight;
    dom.style.left = `${left}px`;
    dom.style.top = `${below ? r.bottom + 6 : Math.max(8, r.top - h - 6)}px`;
    shown = dom;
  }, delay);
}
