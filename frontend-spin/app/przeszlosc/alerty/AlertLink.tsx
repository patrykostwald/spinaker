"use client";
import { useEffect, useState } from 'react';
import { Bar, Foot, nb, useStandalone } from '../ui';

/** Link z e-maila alertu: potwierdzenie (?potwierdz=) albo wypisanie jednym kliknięciem (?wypisz=, &wszystkie=1). */
export function AlertLink() {
  useStandalone();
  const [state, setState] = useState<'working' | 'confirmed' | 'unsubscribed' | 'error' | 'none'>('working');
  const [info, setInfo] = useState<{ label?: string; url?: string; count?: number; detail?: string }>({});
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const confirm = p.get('potwierdz'), out = p.get('wypisz');
    if (!confirm && !out) { setState('none'); return; }
    const path = confirm ? 'potwierdz' : 'wypisz';
    fetch(`/api/przeszlosc/alerty/${path}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: confirm ?? out, wszystkie: p.get('wszystkie') === '1' }) })
      .then(async r => { const d = await r.json().catch(() => ({})); setInfo(d); setState(r.ok ? (confirm ? 'confirmed' : 'unsubscribed') : 'error'); })
      .catch(() => setState('error'));
    // token nie zostaje w historii przeglądarki
    window.history.replaceState(null, '', '/przeszlosc/alerty');
  }, []);
  const text = {
    working: ['Chwila…', ''],
    confirmed: ['Gotowe', `Obserwujesz: ${info.label ?? ''}. Pierwszy list przyjdzie jutro o 7:00, jeśli pojawi się coś nowego. Rezygnacja jednym kliknięciem z każdego listu.`],
    unsubscribed: ['Wypisano', info.count && info.count > 1 ? `Nie dostaniesz już listów o ${info.count} obserwowanych tematach i osobach.` : `Nie dostaniesz już listów: ${info.label ?? ''}.`],
    error: ['Link nie działa', info.detail ?? 'Link wygasł albo jest niepoprawny. Zapisz się ponownie na stronie tematu lub osoby.'],
    none: ['Alerty przeszłość.today', 'Obserwuj temat albo osobę przyciskiem „Obserwuj” na stronie wyniku. Codziennie o 7:00 jeden list z nowościami.'],
  }[state];
  return <main className="px">
    <Bar />
    <section className="px-card px-alert" aria-live="polite">
      <h1>{text[0]}</h1>
      <p>{nb(text[1])}</p>
      <p className="px-alert__act">{state === 'confirmed' && info.url && <a className="px-btn" href={info.url}>Otwórz teraz</a>}
        <a className="px-more" href="/przeszlosc">Strona główna</a></p>
    </section>
    <Foot />
  </main>;
}
