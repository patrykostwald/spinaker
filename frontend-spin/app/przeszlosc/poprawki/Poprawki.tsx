"use client";
import { useEffect, useState } from 'react';
import { Bar, Foot, nb, useStandalone } from '../ui';
import './poprawki.css';

/**
 * Rejestr poprawek (Śledczy R2, P0-8): sprostowania przyjęte przez zespół. Tylko data, rekord i nazwa; bez treści zgłoszenia
 * i bez danych zgłaszającego. Lista z API (backend/news/przeszlosc_wersja.py). Laws of UX: Common Region (jeden wiersz = jedna poprawka).
 */
type Row = { id: number; date: string; record: string; label: string; href: string };
type Data = { count: number; results: Row[]; note: string };

export function Poprawki() {
  useStandalone();
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch('/api/przeszlosc/poprawki/').then(r => r.ok ? r.json() : Promise.reject(r.status)).then(setData).catch(() => setFailed(true));
  }, []);
  return <main className="px px-pop">
    <Bar />
    <header className="px-pop__hero">
      <h1 className="px-pop__title">Poprawki</h1>
      <p className="px-pop__lead">{nb('Każde sprostowanie sprawdzamy ze źródłem. Tu widać te, które przyjęliśmy i wprowadziliśmy: kiedy i czego dotyczyły. Treści zgłoszeń ani danych zgłaszających nie publikujemy.')}</p>
    </header>
    <section aria-labelledby="pop-h" aria-busy={!data && !failed}>
      <h2 id="pop-h" className="px-sr">Lista poprawek</h2>
      {failed && <p className="px-msg" role="alert">Nie udało się pobrać listy. Spróbuj ponownie.</p>}
      {data && data.results.length === 0 && <p className="px-msg">{nb('Brak w naszych danych przyjętych sprostowań (zakres: zgłoszenia ze statusem „naprawione”).')}</p>}
      {data && data.results.length > 0 && <ul className="px-pop__list">
        {data.results.map(r => <li key={r.id} className="px-pop__row">
          <time dateTime={r.date}>{new Date(r.date).toLocaleDateString('pl-PL')}</time>
          <span className="px-pop__what">{r.href ? <a href={r.href}>{r.label || r.record}</a> : (r.label || r.record)}</span>
          <code>{r.record}</code>
        </li>)}
      </ul>}
    </section>
    <Foot />
  </main>;
}
