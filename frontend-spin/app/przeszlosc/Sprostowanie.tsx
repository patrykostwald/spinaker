"use client";
import { useEffect, useRef, useState, type FormEvent } from 'react';

/**
 * „Zgłoś błąd lub sprostowanie” (Śledczy R1, P0-5): widoczny przycisk przy profilu, spółce i węźle drzewa.
 * Zgłoszenie niesie identyfikator rekordu (np. „osoba:326-donald-tusk”, „ted:157377”), trafia na ten sam
 * adres co „Zgłoś błąd” i jest oznaczone „[Sprostowanie]”. Prawo 2 (Fitts): cel co najmniej 44 px.
 */
export function Sprostowanie({ recordId, label, className = 'px-tool' }: { recordId: string; label: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [contact, setContact] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (open) area.current?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  async function send(event: FormEvent) {
    event.preventDefault();
    setState('sending');
    try {
      const csrf = await (await fetch('/api/auth/csrf/', { credentials: 'include', cache: 'no-store' })).json();
      const response = await fetch('/api/feedback/bug/', { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf.csrfToken },
        body: JSON.stringify({ kind: 'bug', text: `[Sprostowanie] ${recordId}\n${label}\n${text.trim()}`.slice(0, 1200), contact, path: window.location.pathname,
          theme: document.documentElement.dataset.theme === 'light' ? 'light' : 'dark', trail: [], viewport: `${window.innerWidth}x${window.innerHeight}` }) });
      if (!response.ok) throw new Error('send');
      setState('sent'); setText(''); setContact('');
    } catch { setState('error'); }
  }

  return <>
    <button type="button" className={`${className} px-fix__btn`} onClick={() => { setState('idle'); setOpen(true); }} data-record={recordId}>Zgłoś błąd lub sprostowanie</button>
    {open && <div className="px-fix" role="presentation" onClick={e => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div className="px-fix__box" role="dialog" aria-modal="true" aria-labelledby="px-fix-h">
        <h2 id="px-fix-h">Zgłoś błąd lub sprostowanie</h2>
        <p className="px-fix__rec">{label} · <code>{recordId}</code></p>
        {state === 'sent' ? <><p>Dziękujemy. Zgłoszenie trafiło do zespołu. Poprawki sprawdzamy z podanym źródłem.</p>
          <button type="button" className="px-fix__ok" onClick={() => setOpen(false)}>Zamknij</button></> :
        <form onSubmit={send}>
          <label>Co jest nieprawdziwe lub wymaga poprawy? Podaj źródło, jeśli je masz.
            <textarea ref={area} required minLength={5} maxLength={900} rows={4} value={text} onChange={e => setText(e.target.value)} /></label>
          <label>E-mail, jeśli chcesz odpowiedź (nieobowiązkowo)
            <input type="email" maxLength={254} value={contact} onChange={e => setContact(e.target.value)} autoComplete="email" /></label>
          {state === 'error' && <p role="alert" className="px-fix__err">Nie udało się wysłać. Spróbuj za chwilę.</p>}
          <div className="px-fix__act"><button type="submit" className="px-fix__ok" disabled={state === 'sending'}>Wyślij</button>
            <button type="button" onClick={() => setOpen(false)}>Anuluj</button></div>
        </form>}
      </div>
    </div>}
  </>;
}
