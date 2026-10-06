"use client";
import { useEffect, useState, type FormEvent } from 'react';
import { Bar, Foot, Icon, nb, useStandalone } from '../ui';
import './pilot.css';

/**
 * Pilotaż przeszłość.today (plan finansowy 6.10, ruch 9): dla kogo, co dostajesz, równe zaproszenie dla obu stron sceny.
 * Formularz -> zgłoszenie (SalesLead 'pilot') -> link potwierdzający w e-mailu -> właściciel przyznaje pilota Pro w panelu.
 */
const WHO: [string, string, string][] = [
  ['people', 'Dziennikarze śledczy', 'Freelancerzy i reporterzy, którzy sprawdzają ludzi, pieniądze i decyzje.'],
  ['media', 'Redakcje lokalne', 'Małe zespoły bez działu researchu, które potrzebują faktów szybko.'],
  ['institution', 'Organizacje strażnicze', 'NGO patrzące władzy na ręce, z każdej strony sceny.'],
  ['record', 'Zespoły z grantami', 'Projekty IJ4EU i Journalismfund: narzędzie jako pozycja w budżecie.'],
];
const GET: [string, string][] = [
  ['Pełny dostęp Pro przez 60 dni', 'Bez opłat i bez karty. Po pilotażu sam decydujesz, czy zostajesz.'],
  ['Kto, co i kiedy w temacie', 'Wypowiedzi polityków, druki i głosowania Sejmu, KRS i przetargi na jednej osi czasu.'],
  ['Profil osoby i alerty', 'Historia wypowiedzi i głosowań, odstępstwa od klubu, codzienny list o nowościach.'],
  ['Bezpośredni kanał do zespołu', 'Zgłaszasz brakujące dane i funkcje; odpowiadamy w 2 dni robocze.'],
];
const ORG: [string, string][] = [['redakcja', 'Redakcja lub dziennikarz'], ['ngo', 'Organizacja pozarządowa'], ['nauka', 'Uczelnia lub think tank'], ['inne', 'Inne']];

export function PilotPage() {
  useStandalone();
  const [form, setForm] = useState({ name: '', organisation: '', org_type: 'redakcja', email: '', message: '' });
  const [privacy, setPrivacy] = useState(false);
  const [newsletter, setNewsletter] = useState(false);
  const [trap, setTrap] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [confirmed, setConfirmed] = useState<'' | 'ok' | 'error'>('');
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('potwierdz');
    if (!token) return;
    window.history.replaceState(null, '', '/przeszlosc/pilot');
    fetch('/api/leady/potwierdz/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) })
      .then(r => setConfirmed(r.ok ? 'ok' : 'error')).catch(() => setConfirmed('error'));
  }, []);
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!privacy) { setState('error'); setMessage('Zaznacz zgodę na kontakt w sprawie pilotażu.'); return; }
    setState('sending');
    try {
      const r = await fetch('/api/przeszlosc/pilot/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, privacy, newsletter, website: trap }) });
      const data = await r.json().catch(() => ({}));
      if (r.status === 429) { setState('error'); setMessage('Za dużo prób. Spróbuj za godzinę.'); return; }
      if (!r.ok) { setState('error'); setMessage(data.detail ?? 'Nie udało się wysłać. Spróbuj ponownie.'); return; }
      setState('done'); setMessage(data.detail ?? 'Sprawdź skrzynkę.');
    } catch { setState('error'); setMessage('Brak połączenia. Spróbuj ponownie.'); }
  }

  return <main className="px">
    <Bar />
    <header className="px-pilot__hero">
      <p className="px-kicker"><span className="px-dot" />Pilotaż · jesień 2026</p>
      <h1>{nb("Sprawdzaj władzę szybciej,")}<br />{nb("z danymi w jednym miejscu")}</h1>
      <p className="px-pilot__lead">{nb('Zapraszamy 10 zespołów do bezpłatnego pilotażu przeszłość.today. Zapraszamy redakcje i dziennikarzy z różnych stron sceny politycznej na tych samych warunkach. Nie pytamy o poglądy.')}</p>
      {confirmed && <p className={confirmed === 'ok' ? 'px-pilot__ok' : 'px-pilot__err'} role="status">{confirmed === 'ok'
        ? nb('Dziękujemy, zgłoszenie potwierdzone. Odezwiemy się w ciągu 2 dni roboczych.')
        : nb('Link wygasł albo jest niepoprawny. Wyślij formularz ponownie.')}</p>}
      <p><a className="px-btn" href="#zgloszenie">Zgłoś zespół</a></p>
    </header>

    <section aria-labelledby="dla-kogo">
      <h2 className="px-h2" id="dla-kogo">Dla kogo</h2>
      <div className="px-pilot__grid">{WHO.map(([icon, title, text]) => <article className="px-card px-pilot__card" key={title}>
        <span className="px-pilot__ic"><Icon name={icon} size={20} /></span>
        <div><h3>{title}</h3><p>{nb(text)}</p></div>
        <footer />
      </article>)}</div>
    </section>

    <section aria-labelledby="co-dostajesz">
      <h2 className="px-h2" id="co-dostajesz">Co dostajesz</h2>
      <ol className="px-pilot__get">{GET.map(([title, text], i) => <li key={title}><b>{i + 1}</b><div><h3>{title}</h3><p>{nb(text)}</p></div></li>)}</ol>
    </section>

    <section aria-labelledby="zasady" className="px-pilot__rules">
      <h2 className="px-h2" id="zasady">Te same zasady dla wszystkich</h2>
      <ul>
        <li>{nb('Każdy zespół dostaje ten sam zakres i ten sam czas pilotażu, niezależnie od profilu redakcji.')}</li>
        <li>{nb('Pilotaż nie daje wpływu na dane, kryteria ani diagnozy Dr. Spina.')}</li>
        <li>{nb('Pokazujemy tylko osoby publiczne i dokumenty z urzędowych źródeł, z linkiem do oryginału.')}</li>
        <li>{nb('Po pilotażu cennik jest jeden dla wszystkich. Nic nie przedłuża się samo.')}</li>
      </ul>
    </section>

    <section aria-labelledby="zgloszenie-h" id="zgloszenie" className="px-card px-pilot__form">
      <h2 className="px-h2" id="zgloszenie-h">Zgłoś zespół</h2>
      {state === 'done' ? <div role="status"><p>{message}</p><p className="px-note">{nb('Nie widzisz listu? Sprawdź folder z ofertami i spamem.')}</p></div> :
        <form onSubmit={send} noValidate>
          <div className="px-pilot__fields">
            <label className="px-follow__field"><span>Imię i nazwisko</span><input required autoComplete="name" value={form.name} onChange={set('name')} /></label>
            <label className="px-follow__field"><span>Redakcja lub organizacja</span><input autoComplete="organization" value={form.organisation} onChange={set('organisation')} /></label>
            <label className="px-follow__field"><span>Kim jesteś</span><select value={form.org_type} onChange={set('org_type')}>{ORG.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label className="px-follow__field"><span>E-mail</span><input type="email" required autoComplete="email" inputMode="email" value={form.email} onChange={set('email')} /></label>
            <label className="px-follow__field px-pilot__wide"><span>Nad czym pracujesz? (opcjonalnie)</span><textarea rows={3} maxLength={2000} value={form.message} onChange={set('message')} /></label>
          </div>
          <input className="px-sr" tabIndex={-1} autoComplete="off" aria-hidden="true" name="website" value={trap} onChange={e => setTrap(e.target.value)} />
          <label className="px-follow__check"><input type="checkbox" checked={privacy} onChange={e => setPrivacy(e.target.checked)} />
            <span>{nb('Zgadzam się na kontakt w sprawie pilotażu (iapply sp. z o.o., operator przeszłość.today).')} <a href="https://spin.clinic/polityka-prywatnosci">Prywatność</a></span></label>
          <label className="px-follow__check"><input type="checkbox" checked={newsletter} onChange={e => setNewsletter(e.target.checked)} />
            <span>{nb('Zgadzam się na e-maile przeszłość.today o pilotażu i nowych funkcjach. Mogę się wypisać jednym kliknięciem.')} (opcjonalnie)</span></label>
          {state === 'error' && <p className="px-pilot__err" role="alert">{message}</p>}
          <div className="px-follow__act"><button className="px-btn" type="submit" disabled={state === 'sending'}>{state === 'sending' ? 'Wysyłam…' : 'Wyślij zgłoszenie'}</button>
            <span className="px-note">{nb('Potwierdzisz je linkiem z e-maila.')}</span></div>
        </form>}
    </section>
    <Foot />
  </main>;
}
