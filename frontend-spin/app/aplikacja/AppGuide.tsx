'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useFeature, NewsletterSignup } from '@spin-clinic/ui';
import { HASH_INSTALL } from '../../lib/pwa';
import { PWA_INSTALL_EVENT, PWA_PUSH_EVENT, PWA_STATE_EVENT, type PwaState } from '../PwaControls';
import './aplikacja.css';

const platforms = [
  { id: 'android', title: 'Android (Chrome)', steps: ['Otwórz spin.clinic w Chrome.', 'Naciśnij „Zainstaluj aplikację” poniżej albo wybierz w menu ⋮ „Zainstaluj aplikację”.', 'Uruchamiaj z ekranu głównego jak każdą aplikację.'], note: 'Powiadomienia działają od razu po zgodzie.' },
  { id: 'ios', title: 'iPhone i iPad (Safari)', steps: ['Otwórz spin.clinic w Safari, nie w przeglądarce wbudowanej w inną aplikację.', 'Wybierz Udostępnij → Do ekranu początkowego → Dodaj.', 'Uruchom aplikację z ekranu początkowego.'], note: 'Wymaga iOS 16.4. Powiadomienia tylko z zainstalowanej aplikacji.' },
  { id: 'desktop', title: 'Komputer (Chrome, Edge)', steps: ['Otwórz spin.clinic w Chrome lub Edge.', 'Kliknij ikonę instalacji w pasku adresu albo przycisk poniżej.', 'Uruchamiaj z menu Start lub Docka.'], note: 'Okno aplikacji działa bez paska przeglądarki.' },
];

export function AppGuide() {
  const push = useFeature('PUSH_ENABLED');
  const accounts = useFeature('ACCOUNTS_ENABLED');
  const alerts = push && accounts;
  const [state, setState] = useState<PwaState>({ installed: false, canPrompt: false, ios: false });
  useEffect(() => {
    if (window.__scPwa) setState(window.__scPwa);
    const onState = (event: Event) => setState((event as CustomEvent<PwaState>).detail);
    window.addEventListener(PWA_STATE_EVENT, onState);
    return () => window.removeEventListener(PWA_STATE_EVENT, onState);
  }, []);
  const status = state.installed ? 'Aplikacja jest zainstalowana na tym urządzeniu.' : state.ios ? 'Na iPhonie i iPadzie instalacja odbywa się przez Udostępnij → Do ekranu początkowego.' : state.canPrompt ? 'Ta przeglądarka pozwala zainstalować aplikację jednym przyciskiem.' : 'Jeśli nie widzisz przycisku instalacji, użyj menu przeglądarki.';
  return <div className="sc-appguide">
    <header className="sc-appguide__head">
      <p className="sc-appguide__kicker">Aplikacja i alerty</p>
      <h1>Aplikacja spin.clinic</h1>
      <p>Klinika, przekazy dnia i alerty o wpisach wybranych osób na ekranie telefonu. Bez sklepu z aplikacjami, bez opłat.</p>
    </header>

    <section aria-labelledby="app-install">
      <h2 id="app-install">Instalacja</h2>
      <div className="sc-appguide__grid">
        {platforms.map(item => <article key={item.id} className="sc-appguide__box sc-appguide__box--steps" data-platform={item.id}>
          <h3>{item.title}</h3>
          <ol>{item.steps.map(step => <li key={step}>{step}</li>)}</ol>
          <p className="sc-appguide__foot">{item.note}</p>
        </article>)}
      </div>
      <div className="sc-appguide__actions">
        <button type="button" className="sc-appguide__primary" disabled={state.installed} onClick={() => window.dispatchEvent(new Event(PWA_INSTALL_EVENT))}>{state.installed ? 'Zainstalowano' : 'Zainstaluj aplikację'}</button>
        <p role="status" aria-live="polite">{status}</p>
      </div>
    </section>

    <section aria-labelledby="app-alerts">
      <h2 id="app-alerts">Alert o wpisie wybranej osoby</h2>
      <div className="sc-appguide__grid">
        <article className="sc-appguide__box">
          <h3>1. Obserwuj osobę</h3>
          <p>Zaloguj się i na stronie osoby wybierz, o czym chcesz wiedzieć: nowe wpisy, diagnozy lub tylko mocny spin.</p>
          <p className="sc-appguide__foot"><Link href="/osoby-publiczne">Osoby publiczne →</Link></p>
        </article>
        <article className="sc-appguide__box">
          <h3>2. Włącz powiadomienia</h3>
          <p>Na tym urządzeniu zezwól na powiadomienia i zaznacz temat „Obserwowani”. Na iPhonie najpierw zainstaluj aplikację.</p>
          <p className="sc-appguide__foot">{alerts
            ? <button type="button" onClick={() => window.dispatchEvent(new Event(PWA_PUSH_EVENT))}>Włącz alerty na tym urządzeniu</button>
            : <span>Alerty push ruszą wkrótce.</span>}</p>
        </article>
        <article className="sc-appguide__box">
          <h3>3. Ustaw ciszę nocną</h3>
          <p>Wybierz godziny ciszy i osoby, które mogą Cię obudzić. Odłożone alerty dostaniesz po zakończeniu ciszy.</p>
          <p className="sc-appguide__foot">{accounts ? <Link href="/konto/alerty">Ustawienia alertów →</Link> : <span>Wymaga konta.</span>}</p>
        </article>
      </div>
      {!alerts && <div className="sc-appguide__signup"><NewsletterSignup source="aplikacja" appLaunch /></div>}
      <p className="sc-appguide__legal">Powiadomienia wysyła iapply sp. z o.o. za Twoją zgodą; wycofasz ją w oknie powiadomień. <Link href="/polityka-prywatnosci">Prywatność</Link> · <a href={HASH_INSTALL}>Okno instalacji</a></p>
    </section>
  </div>;
}
