"use client";
import { useMemo } from 'react';
import { useFeature } from '@spin-clinic/ui';
import {
  normalizeBlock, pairDate, PositionPairs, POSITION_PAIRS_ANCHOR, POSITION_PAIRS_TITLE,
  type PositionPairsBlock,
} from '@spin-clinic/ui/kit';

/**
 * „Wcześniej i teraz” w profilu osoby (przeszłość.today) - zlecenie właściciela 13.10.2026. Neutralna: dane obok siebie, bez oceny;
 * ta sama miara dla każdej osoby. Dane: klucz `position_pairs` odpowiedzi GET /api/przeszlosc/osoba/<ident>/ (API-v3.md, sekcja 5);
 * całość za flagą NEXT_PUBLIC_POSITION_PAIRS (w podglądzie właściciela cookie sc_preview) i tylko gdy API zwróciło pary.
 *
 * Składniki do wpięcia w PersonProfile.tsx / Najwazniejsze.tsx (patrz gust/spin/port/etap-port-fe-pary.md):
 *   - `usePairsBlock(data.position_pairs)` -> blok albo null;
 *   - `<PairsSection block={block} />` w <div className="px-main"> tuż przed sekcją "Oś czasu" (id #wczesniej-i-teraz);
 *   - `<PairsTile block={block} stamp={...} />` jako pasek na końcu landingu (po kaflu "media");
 *   - wpis spisu sekcji: [POSITION_PAIRS_ANCHOR, POSITION_PAIRS_TITLE] tylko gdy blok istnieje.
 * Kafel nie ma licznika: pokazuje temat najnowszego zestawienia i daty obu wypowiedzi (kolejność z API: wg daty B).
 */
export function usePairsBlock(raw: unknown): PositionPairsBlock | null {
  const enabled = useFeature('POSITION_PAIRS_ENABLED');
  return useMemo(() => {
    if (!enabled) return null;
    const block = normalizeBlock(raw);
    return block && (block.paused || block.items.length) ? block : null;
  }, [enabled, raw]);
}

export const PAIRS_INDEX_ENTRY: [string, string] = [POSITION_PAIRS_ANCHOR, POSITION_PAIRS_TITLE];

/** Sekcja z pełną listą (id #wczesniej-i-teraz, pary mają kotwice #stanowiska-<id> jak w powiadomieniu z API). */
export function PairsSection({ block }: { block: PositionPairsBlock | null }) {
  if (!block) return null;
  return <div className="pt-pairs"><PositionPairs block={block} headingId="pp-pary-h" /></div>;
}

const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };

/** Kafel landingu w formie paska (klasy kafli landingu: najwazniejsze.css): etykieta, temat najnowszego zestawienia, daty, odnośnik do sekcji. */
export function PairsTile({ block, stamp }: { block: PositionPairsBlock | null; stamp: string }) {
  if (!block || block.paused || !block.items.length) return null;
  const latest = block.items[0];
  return <article id="pt-t-pary" className="pt-tile pt-tile--strip" data-tile="pary" data-state="ok" aria-labelledby="pt-t-pary-h">
    <header className="pt-tile__top">
      <h3 id="pt-t-pary-h" className="pt-tile__l">{POSITION_PAIRS_TITLE}</h3>
      <div className="pt-tile__vu"><div className="pt-tile__v" data-pt-value>{latest.topic}</div></div>
    </header>
    <div className="pt-tile__b">
      <p className="pt-tile__x">Wcześniej: {pairDate(latest.a.date)}. Teraz: {pairDate(latest.b.date)}. Dwie wypowiedzi obok siebie, bez oceny.</p>
    </div>
    <footer className="pt-tile__f">
      <p className="pt-tile__source" data-pt-source>Źródło: {[latest.a, latest.b].map((side, i) => <span key={i}>{i > 0 ? ', ' : ''}
        <a href={side.source.url} target="_blank" rel="noopener noreferrer">{host(side.source.url)}<i aria-hidden="true"> ↗</i></a></span>)}{' · '}
        <time data-pt-stamp>{stamp}</time></p>
      <a className="pt-tile__more" href={`#${POSITION_PAIRS_ANCHOR}`} aria-label={`Zobacz obok siebie: ${POSITION_PAIRS_TITLE}`}>Zobacz obok siebie →</a>
    </footer>
  </article>;
}
