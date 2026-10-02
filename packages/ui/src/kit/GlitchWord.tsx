"use client";

import { useEffect, useState } from "react";

/**
 * Słowo, które co kilka sekund na chwilę „psuje się” w znaki (#, %, ▒…) i składa z powrotem (właściciel 3.10.2026:
 * przekaz, który się psuje). Każda litera ma stałe miejsce, więc tekst obok nie skacze. Czytniki ekranu słyszą
 * zwykłe słowo, a przy ograniczonych animacjach w systemie nic się nie rusza.
 */
const NOISE = "#%&@$*▒░/\\<>?!";
const PERIOD = 5200;
const STEP = 55;
const STEPS = 7;

export function GlitchWord({ word }: { word: string }) {
  const [shown, setShown] = useState<string[]>(() => [...word]);

  useEffect(() => {
    if (typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const letters = [...word];
    let step = 0;
    let tick: ReturnType<typeof setInterval> | undefined;
    const run = () => {
      step = 0;
      tick = setInterval(() => {
        step += 1;
        // rozpad do połowy, potem składanie z powrotem; coraz mniej szumu pod koniec
        const strength = step <= STEPS / 2 ? step / (STEPS / 2) : (STEPS - step) / (STEPS / 2);
        setShown(letters.map(letter => (letter !== " " && Math.random() < strength * 0.4 ? NOISE[Math.floor(Math.random() * NOISE.length)] : letter)));
        if (step >= STEPS) { clearInterval(tick); setShown(letters); }
      }, STEP);
    };
    const start = setTimeout(run, 1600);
    const loop = setInterval(run, PERIOD);
    return () => { clearTimeout(start); clearInterval(loop); if (tick) clearInterval(tick); };
  }, [word]);

  return <span className="sc-glitch" aria-label={word}>{[...word].map((letter, index) => (
    <span key={index} className="sc-glitch__l" data-g={shown[index] !== letter ? shown[index] : undefined} aria-hidden="true">{letter}</span>
  ))}</span>;
}
