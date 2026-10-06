"use client";
import { useEffect, useState } from 'react';
import { Bar, Foot, Icon, nb, useStandalone, type Access } from '../ui';
import './funkcje.css';

/**
 * „Co potrafi przeszłość.today” (właściciel 7.10: „nie publikujmy cen, dajmy wszystkie funkcjonalności”).
 * Lista z API (backend/news/przeszlosc_dostep.py: FEATURES), bez cen. Równe boksy: ikona i tytuł przy górze, opis i przykład
 * w środku, odnośnik przy dole; przed odpowiedzią API te same boksy jako szkielet, żeby nic nie skakało.
 * Laws of UX: Common Region (boks = funkcja), Similarity (jeden styl), Fitts (odnośnik 44 px), Von Restorff (jeden przycisk).
 */
type Feature = { id: string; icon: string; title: string; text: string; example: string; href: string; tier: string; open: boolean };
type Data = Access & { features: Feature[] };
const SKELETON = 18;

export function Funkcje() {
  useStandalone();
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch('/api/przeszlosc/funkcje/').then(r => r.ok ? r.json() : Promise.reject(r.status)).then(setData).catch(() => setFailed(true));
  }, []);
  const items = data?.features ?? [];
  return <main className="px px-fx">
    <Bar />
    <header className="px-fx__hero">
      <h1 className="px-fx__title">{nb('Co potrafi przeszłość.today')}</h1>
      <p className="px-fx__lead">{nb('Każda funkcja poniżej działa już dziś na danych publicznych: Sejm, KRS, fundusze UE, wpisy polityków i media. Każdy wynik prowadzi do oryginału.')}</p>
    </header>

    <section aria-labelledby="fx-h" aria-busy={!data && !failed}>
      <h2 id="fx-h" className="px-sr">Lista funkcji</h2>
      {failed && <p className="px-msg" role="alert">Nie udało się pobrać listy funkcji. Spróbuj ponownie.</p>}
      {!failed && <ul className="px-fx__grid">
        {data ? items.map(f => <li key={f.id} className="px-fx__card">
          <div className="px-fx__top"><span className="px-fx__ic"><Icon name={f.icon} size={20} /></span><h3 title={f.title}>{f.title}</h3>
            {!f.open && <span className="px-fx__tag">pilotaż</span>}</div>
          <div className="px-fx__body"><p>{nb(f.text)}</p><p className="px-fx__ex"><span>Przykład:</span> {nb(f.example)}</p></div>
          <a className="px-fx__go" href={f.href} {...(f.href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
            aria-label={`${f.title}: otwórz`}>Otwórz<span aria-hidden="true">{f.href.startsWith('http') ? '↗' : '→'}</span></a>
        </li>) : Array.from({ length: SKELETON }, (_, i) => <li key={i} className="px-fx__card px-fx__card--wait" aria-hidden="true" />)}
      </ul>}
    </section>

    <section className="px-cta" aria-labelledby="fx-cta-h">
      <div>
        <h2 id="fx-cta-h">{nb('Dla redakcji i zespołów')}</h2>
        <p>{nb('W becie wszystkie funkcje są otwarte dla każdego. Zespołom pomagamy we wdrożeniu, a warunki po becie ustalamy indywidualnie, te same dla wszystkich.')}</p>
      </div>
      <a className="px-btn" href="/przeszlosc/pilot">Zgłoś zespół do pilotażu</a>
    </section>
    <Foot />
  </main>;
}
