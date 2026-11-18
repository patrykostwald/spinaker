import type { CSSProperties } from 'react';
import type { Ksztalt, } from './warstwy';
import { IKONY, metaStatusu, metaWarstwy } from './warstwy';
import type { StatusKlucz } from './typy';

/** Ikona warstwy w kolorowej plakietce (kolor + symbol + zawsze obok nazwa: kolor nie jest jedynym nośnikiem). */
export function IkonaWarstwy({ kod, rozmiar = 16 }: { kod: string; rozmiar?: number }) {
  const meta = metaWarstwy(kod);
  return <span className="tz-ikona" style={{ '--tz-kolor': meta.kolor } as CSSProperties} aria-hidden="true">
    <svg viewBox="0 0 24 24" width={rozmiar} height={rozmiar} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d={IKONY[meta.ikona] ?? IKONY.ostrzezenie} />
    </svg>
  </span>;
}

/** Kształt znacznika statusu (taki sam jak na mapie). */
export function KsztaltStatusu({ ksztalt, rozmiar = 16 }: { ksztalt: Ksztalt; rozmiar?: number }) {
  const wspolne = { fill: 'currentColor', stroke: 'currentColor', strokeWidth: 1.5, strokeLinejoin: 'round' as const };
  return <svg className="tz-ksztalt" viewBox="0 0 24 24" width={rozmiar} height={rozmiar} aria-hidden="true">
    {ksztalt === 'kolo' && <circle cx="12" cy="12" r="8" {...wspolne} />}
    {ksztalt === 'romb' && <polygon points="12,3 21,12 12,21 3,12" {...wspolne} />}
    {ksztalt === 'kwadrat' && <rect x="5" y="5" width="14" height="14" {...wspolne} />}
    {ksztalt === 'trojkat' && <polygon points="12,4 21,20 3,20" {...wspolne} />}
    {ksztalt === 'krzyzyk' && <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" />}
    {ksztalt === 'pierscien' && <circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" strokeWidth={3} />}
    {ksztalt === 'szesciokat' && <polygon points="12,3.5 19.5,7.75 19.5,16.25 12,20.5 4.5,16.25 4.5,7.75" fill="none" stroke="currentColor" strokeWidth={3} />}
  </svg>;
}

/** Status: kształt i słowo. */
export function EtykietaStatusu({ status }: { status: StatusKlucz }) {
  const m = metaStatusu(status);
  return <span className="tz-status" data-status={status}><KsztaltStatusu ksztalt={m.ksztalt} rozmiar={14} />{m.etykieta}</span>;
}

export function IkonaOstrzezenia({ rozmiar = 16 }: { rozmiar?: number }) {
  return <svg viewBox="0 0 24 24" width={rozmiar} height={rozmiar} fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={IKONY.ostrzezenie} />
  </svg>;
}
