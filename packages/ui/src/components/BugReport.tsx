"use client";
import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Dialog } from './Dialog';
import { Button } from '../kit';
import { apiWrite } from '../lib/api';
import { journeyTrail } from '../lib/journey';

/**
 * „Zgłoś błąd” (właściciel 5.10): dostępny z każdej strony (lewy pasek, na telefonie „Więcej”).
 * Formularz mówi wprost, co dołączamy: adres strony, rozmiar ekranu, motyw i ostatnie strony tej wizyty.
 */
export function BugReportButton({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'bug' | 'idea'>('bug');
  const [text, setText] = useState('');
  const [contact, setContact] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const path = usePathname() ?? '/';

  async function send(event: React.FormEvent) {
    event.preventDefault();
    setState('sending');
    try {
      const theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
      await apiWrite('/api/feedback/bug/', { kind, text, contact, path, theme, trail: journeyTrail(),
        viewport: `${window.innerWidth}x${window.innerHeight}` });
      setState('sent'); setText(''); setContact('');
    } catch {
      setState('error');
    }
  }

  const close = () => { setOpen(false); if (state === 'sent') setState('idle'); };
  return <>
    <button type="button" className={className ?? 'sc-bug-report__open'} onClick={() => setOpen(true)}>Zgłoś błąd</button>
    <Dialog open={open} onClose={close} title="Zgłoś błąd" className="sc-bug-report">
      {state === 'sent' ? <div className="sc-bug-report__done">
        <p>Dziękujemy. Zgłoszenie trafiło do zespołu.</p>
        <Button type="button" variant="primary" onClick={close}>Zamknij</Button>
      </div> : <form onSubmit={send} className="sc-bug-report__form">
        <div className="sc-bug-report__kind" role="radiogroup" aria-label="Rodzaj zgłoszenia">
          {(['bug', 'idea'] as const).map(value => <button key={value} type="button" role="radio" aria-checked={kind === value}
            onClick={() => setKind(value)}>{value === 'bug' ? 'Coś nie działa' : 'Mam pomysł'}</button>)}
        </div>
        <label>{kind === 'bug' ? 'Co się stało?' : 'Co poprawić?'}
          <textarea required minLength={5} maxLength={1000} rows={5} value={text} onChange={event => setText(event.target.value)}
            placeholder={kind === 'bug' ? 'Np. kliknąłem „Wróć” w spince i nic się nie stało.' : 'Np. chciałbym widzieć datę przy każdym boksie.'} />
        </label>
        <label>E-mail, jeśli chcesz odpowiedź (nieobowiązkowo)
          <input type="email" maxLength={254} value={contact} onChange={event => setContact(event.target.value)} autoComplete="email" />
        </label>
        <p className="sc-bug-report__note">Dołączymy: adres tej strony ({path}), rozmiar ekranu, motyw i ostatnie odwiedzone strony. Nic więcej.</p>
        {state === 'error' && <p role="alert" className="sc-bug-report__error">Nie udało się wysłać. Spróbuj za chwilę.</p>}
        <Button type="submit" variant="primary" loading={state === 'sending'} disabled={text.trim().length < 5}>Wyślij</Button>
      </form>}
    </Dialog>
  </>;
}
