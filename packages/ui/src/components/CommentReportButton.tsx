"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { COMMENT_REPORT_REASONS, reportComment, useOwnerId, type CommentReportReason } from '../lib/personal';
import { AccountDialog } from './AccountDialog';
import { Button } from '../kit';

/** Widoczny, ale nienachalny przycisk zgłoszenia komentarza do moderacji. */
export function CommentReportButton({ kind, opinionId, author }: { kind: 'article' | 'thread'; opinionId: number; author: string }) {
  const uid = useId();
  const { ownerId } = useOwnerId();
  const [open, setOpen] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [reason, setReason] = useState<CommentReportReason | ''>('');
  const [details, setDetails] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstOption = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open) firstOption.current?.focus(); }, [open]);

  function close() {
    setOpen(false); setError('');
    window.requestAnimationFrame(() => trigger.current?.focus());
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason) { setError('Wybierz powód zgłoszenia.'); return; }
    setPending(true); setError('');
    try { await reportComment(kind, opinionId, reason, details.trim()); setDone(true); setOpen(false); }
    catch (reasonError) { setError(reasonError instanceof Error ? reasonError.message : 'Nie udało się wysłać zgłoszenia.'); }
    finally { setPending(false); }
  }

  if (done) return <p role="status" className="sc-comment-report-done">Zgłoszenie trafiło do moderacji. Dziękujemy.</p>;

  return (
    <div className="sc-comment-report">
      {!open && (
        <Button ref={trigger} type="button" variant="quiet" size="sm" className="sc-comment-report-link" aria-expanded={false} aria-controls={`${uid}-form`}
          onClick={() => (ownerId ? setOpen(true) : setLoginOpen(true))}>
          Zgłoś komentarz<span className="sr-only"> użytkownika @{author}</span>
        </Button>
      )}
      {open && (
        <form id={`${uid}-form`} className="sc-comment-report-form" onSubmit={submit} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
          <fieldset>
            <legend>Dlaczego zgłaszasz komentarz @{author}?</legend>
            {COMMENT_REPORT_REASONS.map((option, index) => (
              <label key={option.value}>
                <input ref={index === 0 ? firstOption : undefined} type="radio" name={`${uid}-reason`} value={option.value}
                  checked={reason === option.value} onChange={() => setReason(option.value)} />
                {option.label}
              </label>
            ))}
          </fieldset>
          <label className="sc-comment-report-details">Szczegóły (opcjonalnie)
            <textarea rows={2} maxLength={500} value={details} onChange={event => setDetails(event.target.value)} />
          </label>
          <p className="sc-comment-report-note">Zgłoszenie sprawdza moderacja. Nie oceniamy w ten sposób osób ani prawdziwości treści.</p>
          {error && <p role="alert" className="sc-account-error">{error}</p>}
          <div className="sc-comment-report-actions">
            <Button type="submit" variant="secondary" size="sm" loading={pending}>{pending ? 'Wysyłam…' : 'Wyślij zgłoszenie'}</Button>
            <Button type="button" variant="quiet" size="sm" onClick={close}>Anuluj</Button>
          </div>
        </form>
      )}
      {loginOpen && <AccountDialog open={loginOpen} onClose={() => setLoginOpen(false)} />}
    </div>
  );
}
