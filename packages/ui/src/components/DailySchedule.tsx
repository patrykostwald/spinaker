'use client';

import { useEffect, useState } from 'react';

type Row = { key: string; name: string; planned: string; deadline: string; status: string;
  detail: string; description: string; completed_at: string | null; attempt: number;
  attempts: { at: string; detail: string }[]; proposal: string; mail: string };
type Data = { generated_at: string; results: Row[]; health: { checked_at?: string;
  checks: Record<string, { status: string; detail: string }> } };
const labels: Record<string, string> = { done: 'zrobione', waiting: 'czeka', running: 'w toku', late: 'spóźnione',
  repairing: 'naprawiane', alarm: 'alarm', na: 'nie dotyczy', budget: 'wstrzymane: budżet' };
const colors: Record<string, string> = { done: 'ok', waiting: 'off', running: 'ok', late: 'error',
  repairing: 'warn', alarm: 'error', na: 'off', budget: 'warn' };
const hour = (value: string) => new Date(value).toLocaleTimeString('pl-PL', {
  timeZone: 'Europe/Warsaw', hour: '2-digit', minute: '2-digit' });

export function DailySchedule() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    const refresh = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch('/api/staff/daily-schedule/', { credentials: 'include', cache: 'no-store',
          signal: controller.signal, headers: { Accept: 'application/json',
            'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' } });
        if (!response.ok) throw new Error('Nie udało się pobrać harmonogramu.');
        const next: Data = await response.json();
        if (active) { setData(next); setError(''); }
      } catch {
        if (active) setError('Nie udało się odświeżyć harmonogramu. Widoczne dane mogą być nieaktualne.');
      } finally {
        clearTimeout(timeout);
        if (active) timer = setTimeout(() => void refresh(), 60000);
      }
    };
    void refresh();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, []);
  return <section className="sc-agentmap" aria-labelledby="daily-schedule-heading">
    <div className="sc-agentmap__head"><span><strong id="daily-schedule-heading">Harmonogram dnia</strong>
      <small>Europe/Warsaw · problemy na górze · stan {data ? hour(data.generated_at) : 'wczytywanie'}</small></span></div>
    <div className="sc-agentmap__body">
      {error && <p role="alert" className="sc-command-error">{error}</p>}
      {!data && !error && <p role="status">Pobieranie harmonogramu…</p>}
      <div className="sc-agentmap__list">{data?.results.map(row => <details className="sc-agentmap__row" key={row.key} data-status={colors[row.status]}>
        <summary><span className="sc-agentmap__dot" aria-hidden="true" />
          <span className="sc-agentmap__name"><strong>{row.name}</strong><small>{row.detail}</small></span>
          <span className="sc-agentmap__when">{labels[row.status]}{row.status === 'done' && row.completed_at ? ` ${hour(row.completed_at)}` : ''}
            {row.status === 'repairing' ? `, próba ${row.attempt}/3` : ''}</span>
          <span className="sc-agentmap__sched">{row.planned}</span></summary>
        <dl className="sc-agentmap__more"><div><dt>Termin</dt><dd>{row.deadline}</dd></div>
          <div><dt>Cel</dt><dd>{row.description}</dd></div>
          {row.attempts.map((attempt, i) => <div key={attempt.at}><dt>Próba {i + 1}/3 · {hour(attempt.at)}</dt><dd>{attempt.detail}</dd></div>)}
          {row.proposal && <div><dt>Naprawiacz proponuje</dt><dd>{row.proposal}</dd></div>}
          {row.mail && <div><dt>Pilny mail</dt><dd>{row.mail}</dd></div>}
        </dl>
      </details>)}</div>
      <details className="sc-agentmap__group"><summary>Kontrole dostępności co 6 h{data?.health.checked_at ? ` · ${hour(data.health.checked_at)}` : ' · brak wyniku'}</summary>
        {Object.entries(data?.health.checks || {}).map(([key, check]) => <p key={key}><strong>{key.toUpperCase()}</strong>: {check.detail}</p>)}
      </details>
    </div>
  </section>;
}
