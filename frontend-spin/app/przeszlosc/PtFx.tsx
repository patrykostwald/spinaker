"use client";
import { useEffect } from 'react';

/**
 * Dekodowanie liter w stylu terminala (właściciel 13.10, prototyp przeszlosc-v3). Hierarchia ruchu:
 * menu (pasek, indeks akt) = pełne 320 ms; kontrolki w treści (przełączniki, przyciski) = 160 ms i połowa szumu;
 * mikroelementy (chipy, źródła, stopka) = bez dekodowania. Tekst w DOM się nie zmienia: efekt rysuje warstwa aria-hidden
 * nałożona dokładnie na tekst (szerokość bez zmian, czytnik czyta prawdziwy tekst). Reduced motion = brak efektu.
 * Delegacja zdarzeń na dokumencie, bez dotykania węzłów zarządzanych przez React (warstwa jest dokładana i zdejmowana).
 */
const MENU = '.pt-v3 .px-bar__links a, .pt-v3 .pt-idx a';
const CTL = '.pt-v3 :is(.px-seg button, .px-modes button, .px-btn, .px-tool, .px-more, .px-search button)';
const CH = 'ABCDEFGHJKLMNPRSTUWXYZ0123456789<>/_#*+=%';

function decode(el: HTMLElement) {
  if (el.dataset.ptDec) return;
  const menu = el.matches(MENU);
  const D = menu ? 320 : 160, noise = menu ? 1 : .5;
  const node = [...el.childNodes].find(n => n.nodeType === 3 && (n.textContent ?? '').trim());
  if (!node) return;
  const range = document.createRange(); range.selectNodeContents(node);
  const rects = range.getClientRects(); if (rects.length !== 1) return; // tylko tekst w jednej linii
  const b = rects[0], e = el.getBoundingClientRect();
  const txt = (node.textContent ?? '').trim(), n = txt.length;
  const layer = document.createElement('span');
  layer.className = 'pt-dec'; layer.setAttribute('aria-hidden', 'true');
  Object.assign(layer.style, { left: `${b.left - e.left}px`, top: `${b.top - e.top}px`, width: `${b.width + 2}px`, height: `${b.height}px`, lineHeight: `${b.height}px` });
  el.dataset.ptDec = '1'; el.appendChild(layer);
  let t0: number | null = null;
  const frame = (now: number) => {
    if (t0 === null) t0 = now;
    const u = Math.min(1, (now - t0) / D), k = Math.floor(u * n);
    let rest = '';
    for (let i = k; i < n; i++) { const c = txt[i]; rest += /\s/.test(c) || Math.random() > noise ? c : CH[(Math.random() * CH.length) | 0]; }
    const m = document.createElement('span'); m.className = 'pt-dec__m'; m.textContent = rest;
    layer.replaceChildren(document.createTextNode(txt.slice(0, k)), m);
    if (u < 1 && layer.isConnected) requestAnimationFrame(frame);
    else { layer.remove(); delete el.dataset.ptDec; }
  };
  requestAnimationFrame(frame);
}

export function PtFx() {
  useEffect(() => {
    const rm = window.matchMedia('(prefers-reduced-motion: reduce)');
    const target = (ev: Event) => {
      if (rm.matches) return null;
      const el = (ev.target as Element | null)?.closest?.<HTMLElement>(`${MENU}, ${CTL}`);
      return el && !(el as HTMLButtonElement).disabled ? el : null;
    };
    const over = (ev: PointerEvent) => {
      if (ev.pointerType !== 'mouse') return;
      const el = target(ev); if (!el || (ev.relatedTarget instanceof Node && el.contains(ev.relatedTarget))) return;
      decode(el);
    };
    const focus = (ev: FocusEvent) => { const el = target(ev); if (el?.matches(':focus-visible')) decode(el); };
    // zmiana stanu przełącznika (aria-pressed / aria-selected) też dekoduje
    const click = (ev: MouseEvent) => { const el = target(ev); if (el?.matches('.px-seg button, .px-modes button')) setTimeout(() => decode(el), 0); };
    document.addEventListener('pointerover', over);
    document.addEventListener('focusin', focus);
    document.addEventListener('click', click);
    return () => { document.removeEventListener('pointerover', over); document.removeEventListener('focusin', focus); document.removeEventListener('click', click); };
  }, []);
  return null;
}
