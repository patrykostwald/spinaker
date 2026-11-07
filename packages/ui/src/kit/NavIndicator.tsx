"use client";

import { useEffect, useLayoutEffect, useRef } from "react";

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * Jeden współdzielony wskaźnik pozycji menu (seria 2, uwaga właściciela: "animacja zwijania podświetlenia jest poklatkowa").
 * Zamiast tła i kropki animowanych osobno na każdej pozycji: jeden absolutny element w kontenerze menu, przesuwany przez
 * transform (260 ms, cubic-bezier(.22,.61,.36,1)); wysokość i szerokość ustawiane bez animacji (pozycje mają jedną wysokość).
 * Przy wczytaniu stoi od razu na aktywnej pozycji (bez animacji); najechanie / fokus przesuwa go na wskazaną pozycję,
 * wyjście z menu - z powrotem na aktywną. Kontener musi mieć position: relative; pozycje to elementy `a` w kontenerze.
 */
export function NavIndicator({ watch }: { watch?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const ready = useRef(false);

  useIsoLayoutEffect(() => {
    const ind = ref.current;
    const nav = ind?.parentElement;
    if (!ind || !nav) return;
    let frame = 0;
    const current = () => nav.querySelector<HTMLElement>('a[aria-current="page"]');
    const place = (el: HTMLElement | null) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!el || !el.offsetParent) { ind.style.opacity = "0"; return; }
        const nr = nav.getBoundingClientRect(), r = el.getBoundingClientRect();
        ind.style.width = `${r.width}px`;
        ind.style.height = `${r.height}px`;
        ind.style.transform = `translate3d(${Math.round(r.left - nr.left)}px, ${Math.round(r.top - nr.top)}px, 0)`;
        ind.style.opacity = "1";
        ind.dataset.on = el.getAttribute("aria-current") === "page" ? "current" : "hover";
        if (!ready.current) requestAnimationFrame(() => { ready.current = true; ind.dataset.ready = ""; });
      });
    };
    place(current());
    const over = (event: Event) => { const a = (event.target as HTMLElement).closest?.("a"); if (a && nav.contains(a)) place(a as HTMLElement); };
    const back = () => place(current());
    const out = (event: FocusEvent) => { if (!nav.contains(event.relatedTarget as Node)) back(); };
    nav.addEventListener("pointerover", over);
    nav.addEventListener("focusin", over);
    nav.addEventListener("pointerleave", back);
    nav.addEventListener("focusout", out);
    window.addEventListener("resize", back);
    return () => {
      cancelAnimationFrame(frame);
      nav.removeEventListener("pointerover", over);
      nav.removeEventListener("focusin", over);
      nav.removeEventListener("pointerleave", back);
      nav.removeEventListener("focusout", out);
      window.removeEventListener("resize", back);
    };
  }, [watch]);

  return <span ref={ref} className="sc-v3-navind" aria-hidden="true" />;
}
