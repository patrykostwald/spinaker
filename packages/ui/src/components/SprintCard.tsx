'use client';

// Sprint tygodnia (audyt pętli 5.3): bilety budowy z pomysłów agentów, decyzja jednym kliknięciem.
// Prawa UX: Hick (dwa przyciski), Fitts (cele 44 px), Common Region (jedna karta), Similarity (ten sam układ każdego wiersza).
import { useEffect, useState } from 'react';
import { apiWrite } from '../lib/api';

type Ticket = { id: number; title: string; rank: number; effort: 'S' | 'M' | 'L'; executor: 'claude' | 'codex'; status: string;
  due_date: string | null; agent: string; brief: string; acceptance: string[]; commit: string };

const STATUS: Record<string, string> = { proposed: 'do decyzji', approved: 'buduj', in_progress: 'w budowie', done: 'zrobione', dropped: 'odłożone' };
const EFFORT: Record<string, string> = { S: 'mały', M: 'średni', L: 'duży' };
const day = (iso: string | null) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('pl-PL', { day: 'numeric', month: 'numeric' }) : '-');

const CSS = `
.sc-sprint { display: flex; flex-direction: column; gap: 12px; margin: 16px 0; padding: 20px; border: 1px solid var(--sc-line); border-radius: 16px; background: var(--sc-surface); }
.sc-sprint__head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; min-height: 28px; }
.sc-sprint__head h3 { margin: 0; font-size: 1.05rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sc-sprint__count { flex: none; font-size: .75rem; color: var(--sc-text-2); }
.sc-sprint__list { display: flex; flex-direction: column; gap: 8px; margin: 0; padding: 0; list-style: none; }
.sc-sprint__row { display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-rows: auto auto; column-gap: 12px; row-gap: 2px;
  align-items: center; height: 68px; padding: 0 12px; border: 1px solid var(--sc-line); border-radius: 12px; box-sizing: border-box; }
.sc-sprint__title { display: flex; align-items: baseline; gap: 8px; min-width: 0; align-self: end; }
.sc-sprint__title strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .95rem; }
.sc-sprint__tag { flex: none; padding: 1px 6px; border: 1px solid var(--sc-line); border-radius: 999px; font-size: .7rem; color: var(--sc-text-2); }
.sc-sprint__row[data-status="approved"] .sc-sprint__tag, .sc-sprint__row[data-status="in_progress"] .sc-sprint__tag { color: var(--sc-accent); border-color: currentColor; }
.sc-sprint__meta { grid-column: 1; align-self: start; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .8rem; color: var(--sc-text-2); }
.sc-sprint__actions { grid-column: 2; grid-row: 1 / span 2; display: flex; gap: 8px; }
.sc-sprint__actions button { min-width: 44px; min-height: 44px; padding: 0 14px; }
.sc-sprint__foot { margin: 0; font-size: .8rem; color: var(--sc-text-2); overflow-wrap: anywhere; }
.sc-sprint__foot code { font-size: .78rem; }
@media (max-width: 560px) {
  .sc-sprint { padding: 16px; }
  .sc-sprint__row { grid-template-columns: minmax(0, 1fr); grid-template-rows: 22px 20px 44px; align-content: space-between; height: 124px; padding: 12px; }
  .sc-sprint__title { align-self: start; }
  .sc-sprint__meta { align-self: start; }
  .sc-sprint__actions { grid-column: 1; grid-row: 3; }
  .sc-sprint__actions button { flex: 1; }
}`;

export function SprintCard() {
  const [rows, setRows] = useState<Ticket[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    setLoading(true); setError('');
    void fetch('/api/staff/sprint/', { credentials: 'include', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
    }).then(async response => {
      if (!response.ok) throw new Error(response.status === 403 ? 'Dostęp tylko dla personelu.' : 'Nie udało się pobrać sprintu.');
      const data = await response.json();
      if (!controller.signal.aborted) setRows(data.results);
    }).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Nie udało się pobrać sprintu.'); })
      .finally(() => { clearTimeout(timeout); setLoading(false); });
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [revision]);
  const decide = async (ticket: Ticket, decision: 'approved' | 'dropped') => {
    setSaving(ticket.id); setError('');
    try {
      await apiWrite(`/api/staff/sprint/${ticket.id}/decision/`, { decision });
      setRevision(v => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać decyzji.'); }
    finally { setSaving(null); }
  };
  const open = rows.filter(t => t.status !== 'done');
  const waiting = rows.filter(t => t.status === 'proposed').length;
  return <section className="sc-sprint" aria-labelledby="sprint-heading">
    <style>{CSS}</style>
    <div className="sc-sprint__head"><h3 id="sprint-heading">Sprint tygodnia</h3>
      <span className="sc-sprint__count">{loading ? '…' : `${waiting} do decyzji · ${open.length - waiting} w budowie`}</span></div>
    {error && <p role="alert" className="sc-command-error">{error}</p>}
    {!loading && !error && rows.length === 0 && <p className="sc-sprint__foot">Brak biletów. Nowe propozycje w poniedziałek o 6:00.</p>}
    {rows.length > 0 && <ul className="sc-sprint__list">{rows.map(t => <li key={t.id} className="sc-sprint__row" data-status={t.status}
      title={[t.brief, ...t.acceptance.map(a => `- ${a}`)].join('\n')}>
      <span className="sc-sprint__title"><strong>{t.title}</strong><span className="sc-sprint__tag">{STATUS[t.status] || t.status}</span></span>
      <span className="sc-sprint__meta">#{t.id} · {t.agent || 'agent'} · wysiłek {EFFORT[t.effort]} · {t.executor === 'codex' ? 'Codex' : 'Claude'} · termin {day(t.due_date)}{t.commit ? ` · ${t.commit.slice(0, 7)}` : ''}</span>
      <span className="sc-sprint__actions">
        {t.status === 'proposed' && <button type="button" className="sc-command-refresh" disabled={saving !== null} onClick={() => void decide(t, 'approved')}>Buduj</button>}
        {(t.status === 'proposed' || t.status === 'approved') && <button type="button" className="sc-command-filter" disabled={saving !== null} onClick={() => void decide(t, 'dropped')}>Nie teraz</button>}
      </span>
    </li>)}</ul>}
    <p className="sc-sprint__foot">Zlecenia dla Claude i Codexa: <code>python manage.py sprint_zlecenia</code></p>
  </section>;
}
