"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Wejście treści przy przewijaniu (ulubione właściciela: siatka przy przewijaniu, adaptacja v3).
 * SSR i pierwszy render nie ukrywają niczego (treść zawsze w DOM i widoczna bez JS).
 * Ukrywamy tylko elementy, które przy montowaniu są poniżej okna, i pokazujemy je falą po wejściu w widok.
 * prefers-reduced-motion: nic nie ukrywamy (stan końcowy).
 * `ready` - zmienia się, gdy element pojawia się w DOM (np. po wczytaniu danych).
 * Zwraca ref i wartość atrybutu: undefined (bez efektu) | "off" (czeka) | "on"/"in" (widoczne).
 */
export function useWave<T extends HTMLElement>(onValue: "on" | "in" = "in", ready: unknown = true) {
  const ref = useRef<T | null>(null);
  const [state, setState] = useState<"off" | "on" | "in" | undefined>(undefined);
  const armed = useRef(false);
  useEffect(() => {
    const node = ref.current;
    // efekt uruchamiamy raz na element (kolejne odświeżenia danych nie chowają już widocznych wierszy)
    if (!node || armed.current || typeof window === "undefined" || !("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (node.getBoundingClientRect().top < window.innerHeight * 0.92) return;
    armed.current = true;
    setState("off");
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setState(onValue); observer.disconnect(); }
    }, { rootMargin: "0px 0px -8% 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [onValue, ready]);
  return [ref, state] as const;
}
