'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { SectionHeader } from '../kit/SectionHeader';

type Status = 'ok' | 'warn' | 'error' | 'unknown';
type Metric = { label: string; value: string | number | boolean };
type Card = { title: string; status: Status; description: string; last_event: string; metrics: Metric[]; items: Card[] };
type Snapshot = { generated_at: string; sections: Card[] };
const labels: Record<Status, string> = { ok: 'Działa', warn: 'Ostrzeżenie', error: 'Błąd', unknown: 'Brak danych' };
const order: Record<Status, number> = { error: 0, warn: 1, unknown: 2, ok: 3 };
const date = (value: string) => value === 'unknown' ? 'brak danych' : new Date(value).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw' });
const value = (v: Metric['value']) => v === 'unknown' ? 'brak danych' : typeof v === 'boolean' ? (v ? 'Tak' : 'Nie') : typeof v === 'string' && /^\d{4}-\d\d-\d\dT/.test(v) ? date(v) : String(v);

function StatusDot({ status }: { status: Status }) {
  return <span className="sc-command-status" data-status={status}><span aria-hidden="true" />{labels[status]}</span>;
}

function Metrics({ metrics }: { metrics: Metric[] }) {
  return <dl className="sc-command-metrics">{metrics.map((m, i) => <div key={`${m.label}-${i}`}><dt>{m.label}</dt><dd>{value(m.value)}</dd></div>)}</dl>;
}

export function CommandPanel() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch('/api/admin/status/', { credentials: 'include', cache: 'no-store', signal: controller.signal,
        headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' } });
      if (active.current !== controller) return;
      if (response.status === 403 || response.status === 401) {
        setData(null); setForbidden(true); setError(''); return;
      }
      if (!response.ok) throw new Error('Nie udało się pobrać stanu.');
      const snapshot: Snapshot = await response.json();
      if (active.current !== controller) return;
      if (!Array.isArray(snapshot.sections)) throw new Error('Nieprawidłowa odpowiedź API.');
      setData(snapshot); setForbidden(false); setError('');
    } catch {
      if (active.current === controller) setError('Brak połączenia z API. Wyświetlone dane mogą być nieaktualne.');
    } finally {
      clearTimeout(timeout);
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { void refresh(); }, 60000);
    return () => { clearInterval(timer); active.current?.abort(); active.current = null; };
  }, [refresh]);

  const sections = [...(data?.sections || [])].sort((a, b) => order[a.status] - order[b.status]);
  const count = (status: Status) => sections.filter(s => s.status === status).length;
  const summary = count('error') || count('warn') || count('unknown')
    ? `${count('error')} błędów · ${count('warn')} ostrzeżeń · ${count('unknown')} sekcji bez pełnych danych`
    : 'Wszystko działa';

  return <div className="sc-command-panel">
    <SectionHeader variant="page" kicker="spin.clinic · tylko dla personelu" title="Panel dowodzenia"
      subtitle="Status serwisu i pracy redakcji w jednym miejscu."
      action={<button className="sc-command-refresh" onClick={() => void refresh()} disabled={busy}>{busy ? 'Odświeżanie…' : 'Odśwież'}</button>} />
    {forbidden ? <div className="sc-command-banner"><p>Panel jest dostępny wyłącznie dla zalogowanego personelu.</p><Link href="/editor">Przejdź do logowania panelu redakcyjnego →</Link></div> : <>
      <div className="sc-command-banner" role="status" aria-live="polite">
        <strong>{error ? 'Nie można potwierdzić bieżącego stanu' : data ? summary : 'Pobieranie stanu…'}</strong>
        <p>Ostatnie odświeżenie: {data ? date(data.generated_at) : 'brak danych'} · automatycznie co 60 s</p>
      </div>
      {error && <p role="alert" className="sc-command-error">{error}</p>}
      <div className="sc-command-grid">{sections.map(section => <section key={section.title} className="sc-command-card">
        <SectionHeader title={section.title} meta={<StatusDot status={section.status} />} />
        <p>{section.description}</p>
        <Metrics metrics={section.metrics} />
        <p className="sc-command-time">Ostatnie zdarzenie: {date(section.last_event)}</p>
        {section.items.length > 0 && <details><summary>Szczegóły ({section.items.length})</summary><ul className="sc-command-items">
          {[...section.items].sort((a, b) => order[a.status] - order[b.status]).map((item, i) => <li key={`${item.title}-${i}`}>
            <h3>{item.title}</h3><StatusDot status={item.status} /><p>{item.description}</p><Metrics metrics={item.metrics} />
            <p className="sc-command-time">Ostatnie zdarzenie: {date(item.last_event)}</p>
          </li>)}
        </ul></details>}
      </section>)}</div>
    </>}
    <p className="sc-command-install">Na telefonie wybierz w menu przeglądarki „Dodaj do ekranu głównego”. Na iPhonie: Safari → Udostępnij → Do ekranu początkowego. Dane wymagają połączenia z internetem.</p>
  </div>;
}
