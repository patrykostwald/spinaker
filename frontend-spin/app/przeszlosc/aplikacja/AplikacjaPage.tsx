"use client";
import { useEffect, useState } from 'react';
import { PWA_INSTALL_EVENT, PWA_STATE_EVENT, type PwaState } from '../../PwaControls';
import { Bar, Foot, nb, useStandalone } from '../ui';
import { PT_SCREENSHOTS } from '../pwa';
import './aplikacja.css';

/**
 * Aplikacja przeszłość.today (port v3, PWA seria 2): przewodnik instalacji, zrzuty ekranu, co działa bez internetu i jak działają alerty.
 * Treść tylko z tego, co działa w kodzie: pamięć SW (public/sw.js, wariant przeszłości), alerty e-mail (Follow, /api/przeszlosc/alerty/),
 * kanał RSS tematu. Powiadomień push na przeszłości nie ma (PwaControls: pushOn = false dla marki przeszłości).
 * Laws of UX: Jakob (instalacja jak w każdej aplikacji), Hick (trzy platformy, jedna wyróżniona), Proximity i Common Region (boksy bez ramek),
 * Fitts (cele 44 px), Von Restorff (jeden główny przycisk).
 */
type Platform = 'android' | 'ios' | 'desktop';
const PLATFORMS: { id: Platform; title: string; steps: string[]; note: string }[] = [
  { id: 'android', title: 'Android (Chrome)', steps: [
    'Otwórz przeszłość.today w Chrome.',
    'Naciśnij „Zainstaluj” na tej stronie albo wybierz w menu ⋮ „Zainstaluj aplikację”.',
    'Uruchamiaj ikoną z ekranu głównego.'], note: 'Aplikacja otwiera się w osobnym oknie, bez paska adresu.' },
  { id: 'ios', title: 'iPhone i iPad (Safari)', steps: [
    'Otwórz przeszłość.today w Safari, nie w przeglądarce wbudowanej w inną aplikację.',
    'Wybierz Udostępnij → Do ekranu początkowego → Dodaj.',
    'Uruchom aplikację z ekranu początkowego.'], note: 'Safari nie pokazuje przycisku instalacji: dodajesz stronę z menu Udostępnij.' },
  { id: 'desktop', title: 'Komputer (Chrome, Edge)', steps: [
    'Otwórz przeszłość.today w Chrome albo Edge.',
    'Kliknij ikonę instalacji po prawej w pasku adresu albo przycisk „Zainstaluj” na tej stronie.',
    'Uruchamiaj z menu Start lub Docka.'], note: 'Okno aplikacji działa bez zakładek i paska przeglądarki.' },
];
const SHOTS = PT_SCREENSHOTS.filter(s => s.form_factor === 'narrow');

export function AplikacjaPage() {
  useStandalone();
  const [state, setState] = useState<PwaState>({ installed: false, canPrompt: false, ios: false });
  const [android, setAndroid] = useState(false);
  const [mounted, setMounted] = useState(false);
  // pod spin.clinic/przeszlosc manifest jest wspólny (spin.clinic), więc instalacja przeszłości jest możliwa tylko z jej domeny
  const [elsewhere, setElsewhere] = useState(false);
  useEffect(() => {
    setMounted(true);
    const h = location.hostname.replace(/^www\./, '');
    setElsewhere(h !== 'przeszlosc.today' && h !== 'localhost' && h !== '127.0.0.1');
    setAndroid(/Android/i.test(navigator.userAgent));
    if (window.__scPwa) setState(window.__scPwa);
    const onState = (event: Event) => setState((event as CustomEvent<PwaState>).detail);
    window.addEventListener(PWA_STATE_EVENT, onState);
    return () => window.removeEventListener(PWA_STATE_EVENT, onState);
  }, []);
  const here: Platform = state.ios ? 'ios' : android ? 'android' : 'desktop';
  const status = state.installed ? 'Aplikacja jest zainstalowana na tym urządzeniu.'
    : state.ios ? 'Na iPhonie i iPadzie instalacja odbywa się przez Udostępnij → Do ekranu początkowego.'
    : state.canPrompt ? 'Ta przeglądarka pozwala zainstalować aplikację jednym przyciskiem.'
    : 'Jeśli nie widzisz przycisku instalacji, użyj menu przeglądarki.';
  return <div className="px pt-page pa">
    <Bar />
    <header className="pa-head">
      <p className="px-kicker">Aplikacja</p>
      <h1 id="pa-h">Aplikacja przeszłość.today</h1>
      <p className="pa-lead">{nb('Rejestr powiązań osób publicznych z ikoną na ekranie i w osobnym oknie, bez paska przeglądarki. Bez sklepu z aplikacjami: instalujesz prosto z tej strony.')}</p>
      <div className="pa-act">
        {elsewhere
          ? <a className="px-btn" href="https://przeszlosc.today/aplikacja">Otwórz przeszlosc.today</a>
          : <button type="button" className="px-btn" disabled={state.installed} onClick={() => window.dispatchEvent(new Event(PWA_INSTALL_EVENT))}>
            {state.installed ? 'Zainstalowano' : 'Zainstaluj'}</button>}
        <p role="status" aria-live="polite">{mounted ? nb(elsewhere ? 'Aplikację przeszłość.today instalujesz z jej własnego adresu: przeszlosc.today.' : status) : ''}</p>
      </div>
    </header>

    <section className="px-sec" aria-labelledby="pa-inst">
      <h2 id="pa-inst" className="px-h2">Instalacja</h2>
      <ul className="pa-grid">
        {PLATFORMS.map(p => <li key={p.id} className="pa-card" data-platform={p.id} data-here={mounted && here === p.id ? '' : undefined}>
          <h3>{p.title}{mounted && here === p.id && <span className="px-sr"> (to urządzenie)</span>}</h3>
          <ol>{p.steps.map(s => <li key={s}>{nb(s)}</li>)}</ol>
          <p className="pa-card__note">{nb(p.note)}</p>
        </li>)}
      </ul>
    </section>

    <section className="px-sec" aria-labelledby="pa-shots">
      <h2 id="pa-shots" className="px-h2">Tak wygląda</h2>
      <ul className="pa-shots">
        {SHOTS.map(s => <li key={s.src}><figure>
          <img src={s.src} width={390} height={844} loading="lazy" decoding="async" alt={`Zrzut ekranu aplikacji: ${s.label}`} />
          <figcaption>{nb(s.label)}</figcaption></figure></li>)}
      </ul>
    </section>

    <section className="px-sec" aria-labelledby="pa-how">
      <h2 id="pa-how" className="px-h2">Offline i alerty</h2>
      <div className="pa-two">
        <div className="pa-box">
          <h3>Bez internetu</h3>
          <ul>
            <li>{nb('Strona „Jak to działa” otwiera się też bez sieci, jeśli była wcześniej otwarta.')}</li>
            <li>{nb('Wygląd aplikacji (kod, kroje i ikony) zapisuje się w pamięci urządzenia po pierwszym otwarciu.')}</li>
            <li>{nb('Wyniki (tematy, osoby, głosowania, KRS) pobieramy na bieżąco ze źródeł, więc bez sieci zobaczysz komunikat „Brak połączenia”. Nie zapisujemy ich w pamięci urządzenia.')}</li>
          </ul>
        </div>
        <div className="pa-box">
          <h3>Alerty</h3>
          <ul>
            <li>{nb('Przy temacie jest też kanał RSS, bez konta.')}</li>
            <li>{nb('Powiadomień push na telefonie w tej aplikacji nie ma: alerty przychodzą e-mailem.')}</li>
            <li>{nb('Zapis potwierdzasz linkiem z listu, a wypisujesz jednym kliknięciem z każdej wiadomości.')}</li>
            <li>{nb('Przy temacie albo osobie wybierz „Obserwuj”: codziennie o 7:00 dostaniesz jeden list z nowościami. Gdy nic nowego nie ma, nie piszemy.')}</li>
          </ul>
        </div>
      </div>
      <p className="pa-more"><a className="px-link" href="/przeszlosc/jak-to-dziala">Jak to działa&nbsp;→</a><a className="px-link" href="/przeszlosc/funkcje">Co potrafi przeszłość.today&nbsp;→</a></p>
    </section>
    <Foot />
  </div>;
}
