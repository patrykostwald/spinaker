"use client";

/**
 * FoldedSection — sekcja strony ładuje się ZŁOŻONA (nagłówek + jeden rząd / `preview`) i rozwija się
 * RAZ, gdy jej nagłówek przetnie pasmo fokalne (docs/UI_KIT_PLAN.md → «Mobilne rozkłady» →
 * «Rozwijanie sekcji przy przewijaniu»). Później nigdy się nie składa z powrotem.
 *
 * Nagłówek jest lepki (`position: sticky`) pod uszczelnionym `CompactHeader` i ustępuje miejsca
 * kolejnemu nagłówkowi — to naturalne zachowanie CSS `sticky` przy równych `top`, żadnego JS.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { RevealHeight } from "../motion/Reveal";
import { cn } from "../../lib/utils";
import { FOCAL_BAND, focalBandRootMargin } from "./useFocalBand";

export type FoldedSectionProps = {
  /** Tytuł sekcji — zawsze widoczny, lepki. */
  title: ReactNode;
  /** To, co widać w stanie złożonym: nagłówek + pierwszy rząd/karta. */
  preview: ReactNode;
  /** Pełna treść — wjeżdża po rozwinięciu, kaskadą (RevealHeight → `expand`). */
  children: ReactNode;
  /**
   * Kontener przewijania używany jako korzeń IntersectionObserver — na stoisku witryny to ramka
   * telefonu z `overflow: auto`; na żywej stronie zostaje `null` (korzeń = okno przeglądarki).
   */
  scrollRootRef?: React.RefObject<HTMLElement | null>;
  className?: string;
};

export function FoldedSection({ title, preview, children, scrollRootRef, className }: FoldedSectionProps) {
  const headerRef = useRef<HTMLDivElement | null>(null);
  const [unfolded, setUnfolded] = useState(false);

  useEffect(() => {
    if (unfolded) return;
    const header = headerRef.current;
    if (!header || typeof IntersectionObserver === "undefined") {
      setUnfolded(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const crossed = entries.some((entry) => {
          // Zwykły przypadek: nagłówek WŁAŚNIE przecina pasmo podczas przewijania w dół.
          if (entry.isIntersecting) return true;
          // Brzegowy przypadek: pierwsza sekcja strony startuje już WYŻEJ niż pasmo (jest nad
          // nim od razu przy wczytaniu, bo pasmo leży w środku ekranu, a nagłówek — tuż pod
          // nagłówkiem strony). Taki nagłówek nigdy „nie przetnie” pasma, bo tylko oddala się
          // w górę — licząc od momentu obserwacji, uznajemy go za już przekroczony.
          if (!entry.rootBounds) return false;
          return entry.boundingClientRect.bottom <= entry.rootBounds.top;
        });
        if (crossed) {
          setUnfolded(true);
          observer.disconnect();
        }
      },
      { root: scrollRootRef?.current ?? null, rootMargin: focalBandRootMargin("y", FOCAL_BAND), threshold: 0 },
    );
    observer.observe(header);
    return () => observer.disconnect();
    // Rozwijanie jest jednorazowe: po `unfolded === true` efekt świadomie nie re-obserwuje.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unfolded]);

  return (
    <section className={cn("sc-folded", className)} data-unfolded={unfolded || undefined}>
      <div ref={headerRef} className="sc-folded__header sc-chrome">
        {title}
      </div>
      <div className="sc-folded__preview">{preview}</div>
      <RevealHeight when={unfolded}>{children}</RevealHeight>
    </section>
  );
}
