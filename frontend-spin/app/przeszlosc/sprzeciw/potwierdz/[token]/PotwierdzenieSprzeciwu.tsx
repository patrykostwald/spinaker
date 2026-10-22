"use client";
import { useEffect, useState } from 'react';
import { Bar, Foot, nb, useStandalone } from '../../../ui';
import { confirmMessage } from '../../../informacja-dane';

/**
 * Strona linku z e-maila potwierdzającego sprzeciw (API-v3 sekcja 0): GET /api/przeszlosc/sprzeciw/potwierdz/<token>/
 * -> 200 potwierdzony, 410 "Link wygasł lub został już użyty", 404 nieznany. Nowy wygląd, bez pasków; token tylko
 * z adresu (litery, cyfry, - i _), inaczej od razu stan "nie znaleziono".
 */
export function PotwierdzenieSprzeciwu({ token }: { token: string }) {
  useStandalone();
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    if (!/^[A-Za-z0-9_-]{8,200}$/.test(token)) { setStatus(404); return; }
    fetch(`/api/przeszlosc/sprzeciw/potwierdz/${encodeURIComponent(token)}/`, { cache: 'no-store', credentials: 'include' })
      .then(r => setStatus(r.status)).catch(() => setStatus(0));
  }, [token]);
  const m = status === null ? null : confirmMessage(status);
  return <div className="px pt-page">
    <Bar />
    <section className="px-sec pt-confirm" aria-live="polite">
      <p className="px-kicker">Informacja o danych</p>
      {m ? <><h1>{nb(m.title)}</h1><p className="px-lead">{nb(m.text)}</p>
        <p><a className="px-link" href="/przeszlosc/jak-to-dziala#dane-osob">Jak przetwarzamy dane osób&nbsp;→</a></p></>
        : <h1 role="status">Sprawdzamy link…</h1>}
    </section>
    <Foot />
  </div>;
}
