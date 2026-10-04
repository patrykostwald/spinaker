"use client";
import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Dialog } from './Dialog';
import { Button } from '../kit';
import { apiWrite } from '../lib/api';
import { journeyTrail } from '../lib/journey';

/**
 * „Zgłoś błąd” (właściciel 5.10): ikonka w prawym dolnym rogu, na wysokości ostatniego wiersza lewego menu.
 * Szybki formularz: link do strony (wpisany od razu), krótki opis i e-mail - oba nieobowiązkowe.
 * Formularz mówi wprost, co dołączamy: rozmiar ekranu, motyw i ostatnie strony tej wizyty.
 */
export function BugReportButton({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [link, setLink] = useState('');
  const [text, setText] = useState('');
  const [contact, setContact] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const path = usePathname() ?? '/';

  function start() {
    setLink(window.location.href);
    setState('idle');
    setOpen(true);
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    setState('sending');
    try {
      const theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
      const body = [text.trim(), link.trim() && link.trim() !== window.location.href ? `Link: ${link.trim()}` : ''].filter(Boolean).join('\n');
      await apiWrite('/api/feedback/bug/', { kind: 'bug', text: body, contact, path, theme, trail: journeyTrail(),
        viewport: `${window.innerWidth}x${window.innerHeight}` });
      setState('sent'); setText(''); setContact('');
    } catch {
      setState('error');
    }
  }

  return <>
    <button type="button" className={className ?? 'sc-bug-fab'} onClick={start} aria-label="Zgłoś błąd" title="Zgłoś błąd">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M8 9a4 4 0 0 1 8 0v5a4 4 0 0 1-8 0Z" /><path d="M12 9v9M9.5 5.5 8 4M14.5 5.5 16 4M4 13h4M16 13h4M5 8l3 2M19 8l-3 2M5 19l3-2M19 19l-3-2" />
      </svg>
    </button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Zgłoś błąd" className="sc-bug-report">
      {state === 'sent' ? <div className="sc-bug-report__done">
        <p>Dziękujemy. Zgłoszenie trafiło do zespołu.</p>
        <Button type="button" variant="primary" onClick={() => setOpen(false)}>Zamknij</Button>
      </div> : <form onSubmit={send} className="sc-bug-report__form">
        <label>Link do strony z błędem
          <input type="url" maxLength={500} value={link} onChange={event => setLink(event.target.value)} />
        </label>
        <label>Co nie działa? (krótko, nieobowiązkowo)
          <textarea maxLength={1000} rows={3} value={text} onChange={event => setText(event.target.value)}
            placeholder="Np. kliknąłem „Wróć” w spince i nic się nie stało." />
        </label>
        <label>E-mail, jeśli chcesz odpowiedź (nieobowiązkowo)
          <input type="email" maxLength={254} value={contact} onChange={event => setContact(event.target.value)} autoComplete="email" />
        </label>
        <p className="sc-bug-report__note">Dołączymy też rozmiar ekranu, motyw i ostatnie odwiedzone strony. Nic więcej.</p>
        {state === 'error' && <p role="alert" className="sc-bug-report__error">Nie udało się wysłać. Spróbuj za chwilę.</p>}
        <Button type="submit" variant="primary" loading={state === 'sending'}>Wyślij</Button>
      </form>}
    </Dialog>
  </>;
}
