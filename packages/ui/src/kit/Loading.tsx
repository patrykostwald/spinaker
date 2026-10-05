"use client";

import { useEffect, useState } from "react";

/**
 * Wskaźnik ładowania (właściciel 5.10): małe „ŁADOWANIE” na środku ładującego się elementu, litery szybko przeskakują
 * w znaki jak psujące się słowo „przekaz”. Czytnik ekranu słyszy opis (label); przy ograniczonych animacjach napis stoi.
 */
const WORD = "ŁADOWANIE";
const NOISE = "#%&@$*/<>?!";

export function Loading({ label = "Ładowanie", inline = false }: { label?: string; inline?: boolean }) {
  const [shown, setShown] = useState<string[]>(() => [...WORD]);
  useEffect(() => {
    if (typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // panel designu 5.10: spokojniej (250 ms, rzadziej), a po 3 s szum stoi - zwykłe „ŁADOWANIE”
    const letters = [...WORD];
    const tick = setInterval(() => {
      setShown(letters.map(letter => (Math.random() < 0.15 ? NOISE[Math.floor(Math.random() * NOISE.length)] : letter)));
    }, 250);
    const calm = setTimeout(() => { clearInterval(tick); setShown(letters); }, 3000);
    return () => { clearInterval(tick); clearTimeout(calm); };
  }, []);
  return <span className={`sc-loading${inline ? " sc-loading--inline" : ""}`} role="status" aria-live="polite">
    <span className="sc-sr-only">{label}…</span>
    <span className="sc-loading__word" aria-hidden="true">{[...WORD].map((letter, index) => (
      <span key={index} className="sc-loading__l" data-g={shown[index] !== letter ? shown[index] : undefined}>{letter}</span>
    ))}</span>
  </span>;
}
