'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { apiWrite } from '../lib/api';
import { AgentsPanel } from './AgentsPanel';

type Status = 'ok' | 'warn' | 'error' | 'unknown';
type Reading = number | 'unknown';
type Metric = { label: string; value: string | number | boolean };
type Card = { title: string; status: Status; description: string; last_event: string; metrics: Metric[]; items: Card[]; href?: string; link_label?: string };
type Kpi = { key: string; label: string; today: Reading; yesterday: Reading; unit?: string };
type Series = { key: string; label: string; unit?: string; points: { date: string; value: Reading }[] };
type Wallet = { provider: string; label: string; currency: string; recorded_balance: Reading; recorded_at: string; spent_since: Reading; estimated_balance: Reading; actual_balance: Reading; actual_currency?: string; actual_checked_at?: string; days_remaining: Reading; status: Status; note?: string; tracked?: boolean; signal?: string; signal_at?: string };
type Action = { title: string; status: Status; detail?: string; section?: string };
type Snapshot = { generated_at: string; sections: Card[]; kpis?: Kpi[]; series?: Series[]; wallets?: Wallet[]; actions?: Action[] };
const labels: Record<Status, string> = { ok: 'Działa', warn: 'Uwaga', error: 'Błąd', unknown: 'Brak danych' };
const order: Record<Status, number> = { error: 0, warn: 1, unknown: 2, ok: 3 };
const providers = [['x', 'X API'], ['gemini', 'Gemini / Google AI Studio'], ['anthropic', 'Anthropic']];
const numeric = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const number = (v: Reading | undefined, unit = '') => numeric(v) ? `${v.toLocaleString('pl-PL', { maximumFractionDigits: unit ? 4 : 0 })}${unit ? ` ${unit}` : ''}` : 'brak danych';
const date = (v: string | undefined) => !v || v === 'unknown' || Number.isNaN(Date.parse(v)) ? 'brak danych' : new Date(v).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw', dateStyle: 'short', timeStyle: 'short' });
const value = (v: Metric['value']) => v === 'unknown' ? 'brak danych' : typeof v === 'boolean' ? (v ? 'Tak' : 'Nie') : typeof v === 'string' && /^\d{4}-\d\d-\d\dT/.test(v) ? date(v) : typeof v === 'number' ? v.toLocaleString('pl-PL', { maximumFractionDigits: 6 }) : String(v);
const hasProblem = (card: Card): boolean => card.status !== 'ok' || (card.items || []).some(hasProblem);
const cardStatus = (card: Card): Status => [card.status, ...(card.items || []).map(cardStatus)].sort((a, b) => order[a] - order[b])[0];
const sectionId = (title: string) => `command-${encodeURIComponent(title)}`;
function warsawInput(d: Date) {
  const p = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(d);
  const part = (key: string) => p.find(item => item.type === key)?.value;
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
function warsawIso(input: string) {
  // Try both real Polish offsets. During the autumn overlap choose the earlier occurrence.
  const parsed = ['+02:00', '+01:00'].map(offset => new Date(`${input}:00${offset}`)).find(d => !Number.isNaN(d.getTime()) && warsawInput(d) === input);
  if (!parsed) throw new Error('Ta godzina nie istnieje w strefie Europe/Warsaw. Wybierz inną.');
  return parsed.toISOString();
}
function StatusDot({ status }: { status: Status }) {
  return <span className="sc-command-status" data-status={status}><span aria-hidden="true" />{labels[status]}</span>;
}
function Metrics({ metrics }: { metrics: Metric[] }) {
  return <dl className="sc-command-metrics">{metrics.map((m, i) => <div key={`${m.label}-${i}`}><dt>{m.label}</dt><dd>{value(m.value)}</dd></div>)}</dl>;
}
function Trend({ today, yesterday, unit }: Kpi) {
  if (!numeric(today) || !numeric(yesterday)) return <span className="sc-command-trend">Porównanie: brak danych</span>;
  const delta = today - yesterday;
  return <span className="sc-command-trend"><b aria-hidden="true">{delta > 0 ? '↗' : delta < 0 ? '↘' : '→'}</b> {delta === 0 ? 'Bez zmiany' : `${delta > 0 ? 'Więcej' : 'Mniej'} o ${number(Math.abs(delta), unit)}`} <span>· wczoraj {number(yesterday, unit)}</span></span>;
}
function Sparkline({ series }: { series: Series }) {
  const points = series.points.slice(-7);
  const known = points.map(p => p.value).filter(numeric);
  const max = Math.max(1, ...known);
  const x = (i: number) => 8 + i * 264 / Math.max(1, points.length - 1);
  const y = (v: number) => 66 - (v / max) * 56;
  // Missing observations break the line and are never rendered as zero.
  const path = points.map((p, i) => numeric(p.value) ? `${i && numeric(points[i - 1].value) ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}` : '').join(' ');
  return <article className="sc-command-chart"><h3>{series.label}</h3><p>{series.unit ? `Szacowane · ${series.unit}` : 'Liczba dziennie'} · ostatnie 7 dni</p>
    {known.length ? <svg viewBox="0 0 280 78" role="img" aria-label={`${series.label}: ${points.map(p => `${p.date}: ${number(p.value, series.unit)}`).join('; ')}`}>
      <path d="M8 66H272" className="sc-command-chart-base" /><path d={path} className="sc-command-chart-line" />
      {points.map((p, i) => numeric(p.value) ? <circle key={p.date} cx={x(i)} cy={y(p.value)} r="3"><title>{p.date}: {number(p.value, series.unit)}</title></circle> : null)}
    </svg> : <div className="sc-command-chart-empty">Brak pomiarów</div>}
    <div className="sc-command-chart-axis"><span>{points[0]?.date || 'brak danych'}</span><span>{points[points.length - 1]?.date || ''}</span></div>
    <details className="sc-command-chart-data"><summary>Wartości dzienne</summary><dl>{points.map(p => <div key={p.date}><dt>{p.date}</dt><dd>{number(p.value, series.unit)}</dd></div>)}</dl></details>
  </article>;
}
function DetailCard({ card, onlyProblems, nested = false }: { card: Card; onlyProblems: boolean; nested?: boolean }) {
  const items = [...(card.items || [])].filter(item => !onlyProblems || hasProblem(item)).sort((a, b) => order[a.status] - order[b.status]);
  return <details id={nested ? undefined : sectionId(card.title)} className={nested ? 'sc-command-item' : 'sc-command-card'} open={onlyProblems || undefined}>
    <summary><span>{card.title}</span><StatusDot status={cardStatus(card)} /><span className="sc-command-toggle" aria-hidden="true">+</span></summary>
    <div className="sc-command-card-body"><p>{card.description}</p><Metrics metrics={card.metrics || []} /><p className="sc-command-time">Ostatnie zdarzenie: {date(card.last_event)}</p>
      {card.href && <a href={card.href}>{card.link_label || 'Otwórz szczegóły'}</a>}
      {items.map((item, i) => <DetailCard key={`${item.title}-${i}`} card={item} onlyProblems={onlyProblems} nested />)}
    </div>
  </details>;
}
function WalletCard({ wallet }: { wallet: Wallet }) {
  const days = wallet.days_remaining;
  // Najpierw saldo odczytane z API, potem szacunek (wpisane − wydatki), na końcu samo wpisane saldo.
  const [heading, main, unit] = numeric(wallet.actual_balance) ? ['Saldo z API dostawcy', wallet.actual_balance, wallet.actual_currency || 'USD']
    : numeric(wallet.estimated_balance) ? ['Szacowane saldo', wallet.estimated_balance, wallet.currency]
    : numeric(wallet.recorded_balance) ? ['Wpisane saldo', wallet.recorded_balance, wallet.currency] : ['Saldo', 'unknown' as Reading, wallet.currency];
  const facts: [string, string][] = [];
  if (numeric(wallet.actual_balance)) facts.push(['Odczyt z API', date(wallet.actual_checked_at)]);
  if (numeric(wallet.recorded_balance)) facts.push(['Wpisane saldo', `${number(wallet.recorded_balance, wallet.currency)} · ${date(wallet.recorded_at)}`]);
  if (numeric(wallet.spent_since)) facts.push(['Wydano od wpisu · szacunek', number(wallet.spent_since, wallet.currency)]);
  return <article className="sc-command-wallet" data-status={wallet.status}><div className="sc-command-wallet-head"><h3>{wallet.label}</h3><StatusDot status={wallet.status} /></div>
    {wallet.signal && <p role="alert" className="sc-command-error">{wallet.signal}</p>}
    <span className="sc-command-eyebrow">{heading}</span><strong className="sc-command-balance">{numeric(main) ? number(main, unit) : wallet.signal ? 'brak środków' : 'brak danych'}</strong>
    {(numeric(days) || (numeric(main) && main <= 0)) && <p className="sc-command-runway">{numeric(main) && main <= 0 ? 'Saldo wyczerpane — doładuj portfel' : numeric(days) ? days < 1 ? 'Starczy na mniej niż 1 dzień' : `Starczy na ~${number(days)} dni` : ''}</p>}
    {numeric(days) && <div className="sc-command-wallet-track" role="meter" aria-label="Dni finansowania, skala do 30 dni" aria-valuemin={0} aria-valuemax={30} aria-valuenow={Math.min(30, Math.max(0, days))} aria-valuetext={`Około ${number(days)} dni`}><span style={{ width: `${Math.min(100, Math.max(0, days / 30 * 100))}%` }} /></div>}
    {facts.length > 0 && <dl className="sc-command-wallet-facts">{facts.map(([label, text]) => <div key={label}><dt>{label}</dt><dd>{text}</dd></div>)}</dl>}
  </article>;
}
function WalletForm({ onSaved }: { onSaved: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [failed, setFailed] = useState(false);
  const [recordedAt, setRecordedAt] = useState(() => warsawInput(new Date()));
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;
    const fields = new FormData(event.currentTarget);
    setSaving(true); setMessage(''); setFailed(false);
    try {
      await apiWrite('/api/admin/wallets/', { provider: fields.get('provider'), amount: fields.get('amount'), currency: fields.get('currency'), recorded_at: warsawIso(recordedAt) });
      setMessage('Saldo zapisane.');
      await onSaved();
    } catch (e) { setFailed(true); setMessage(e instanceof Error ? e.message : 'Nie udało się zapisać salda.'); }
    finally { setSaving(false); }
  };
  return <details className="sc-command-wallet-editor"><summary>＋ Wpisz aktualne saldo (po doładowaniu)</summary><form onSubmit={event => void submit(event)}>
    <p>Wpisz całe saldo widoczne u dostawcy na wskazany moment. To nowy punkt odniesienia, nie kwota dodawana do poprzedniego salda.</p>
    <div className="sc-command-form-grid"><label>Dostawca<select name="provider" required>{providers.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Saldo<input name="amount" type="number" min="0" step="0.01" inputMode="decimal" placeholder="0,00" required /></label>
      <label>Waluta<select name="currency" defaultValue="USD"><option>USD</option><option>EUR</option><option>PLN</option></select></label>
      <label>Stan na · Europe/Warsaw<input name="recorded_at" type="datetime-local" value={recordedAt} onChange={event => setRecordedAt(event.target.value)} required /></label></div>
    <p className="sc-command-note">Przy jesiennej zmianie czasu powtórzona godzina oznacza pierwsze wystąpienie (czas letni).</p>
    <button type="submit" className="sc-command-refresh" disabled={saving}>{saving ? 'Zapisywanie…' : 'Zapisz saldo'}</button>
    {message && <p role={failed ? 'alert' : 'status'} className={failed ? 'sc-command-error' : ''}>{message}</p>}
  </form></details>;
}

export function CommandPanel() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(true);
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch('/api/admin/status/', { credentials: 'include', cache: 'no-store', signal: controller.signal,
        headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' } });
      if (active.current !== controller) return;
      if (response.status === 403 || response.status === 401) { setData(null); setForbidden(true); setError(''); return; }
      if (!response.ok) throw new Error('Nie udało się pobrać stanu.');
      const snapshot: Snapshot = await response.json();
      if (active.current !== controller) return;
      if (!Array.isArray(snapshot.sections)) throw new Error('Nieprawidłowa odpowiedź API.');
      setData(snapshot); setForbidden(false); setError('');
    } catch { if (active.current === controller) setError('Brak połączenia z API. Wyświetlone dane mogą być nieaktualne.'); }
    finally { clearTimeout(timeout); if (active.current === controller) { active.current = null; setBusy(false); } }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { if (document.visibilityState === 'visible') void refresh(); }, 60000);
    return () => { clearInterval(timer); active.current?.abort(); active.current = null; };
  }, [refresh]);

  const allSections = [...(data?.sections || [])].sort((a, b) => order[cardStatus(a)] - order[cardStatus(b)]);
  const sections = allSections.filter(section => !onlyProblems || hasProblem(section));
  const actions = [...(data?.actions || [])].filter(action => action.status !== 'ok').sort((a, b) => order[a.status] - order[b.status]);
  const problemCount = allSections.filter(hasProblem).length;
  const wallets = (data?.wallets || []).filter(wallet => wallet.tracked !== false && (!onlyProblems || wallet.status !== 'ok'));
  const worst: Status = error ? 'unknown' : [...actions.map(action => action.status), ...allSections.map(cardStatus)].sort((a, b) => order[a] - order[b])[0] || 'ok';

  return <div className="sc-command-panel sc-command-v2">
    <header className="sc-command-header"><div><span className="sc-command-eyebrow">spin.clinic · operacje</span><h1>Panel dowodzenia</h1></div><button type="button" className="sc-command-refresh" onClick={() => void refresh()} disabled={busy} aria-label="Odśwież stan centrum dowodzenia">{busy ? 'Odświeżanie…' : '↻ Odśwież'}</button></header>
    {forbidden ? <div className="sc-command-banner"><p>Panel jest dostępny wyłącznie dla zalogowanego personelu.</p><Link href="/editor">Przejdź do logowania panelu redakcyjnego →</Link></div> : <>
      <section className="sc-command-health" data-status={worst} aria-label="Zdrowie projektu"><div className="sc-command-health-title" role="status" aria-live="polite"><strong>{error ? 'Nie można potwierdzić bieżącego stanu' : !data ? 'Pobieranie stanu…' : problemCount || actions.length ? `Wymaga uwagi${problemCount ? ` · sekcje: ${problemCount}` : ''}` : 'Wszystko działa'}</strong><StatusDot status={!data ? 'unknown' : worst} /></div>
        {error && <p role="alert" className="sc-command-error">{error}</p>}
        {actions.length > 0 ? <ul className="sc-command-actions sc-command-priority">{actions.slice(0, 1).map((action, i) => <li key={`${action.title}-${i}`}><b>{action.title}</b>{action.detail && <span>{action.detail}</span>}{action.section && (action.section === 'Portfele' || allSections.some(s => s.title === action.section)) && <a href={`#${action.section === 'Portfele' ? 'command-wallets' : sectionId(action.section)}`} onClick={() => { const target = document.getElementById(sectionId(action.section!)); if (target instanceof HTMLDetailsElement) target.open = true; }}>Sprawdź →</a>}</li>)}</ul> : data && problemCount > 0 ? <p>Rozwiń sekcje oznaczone „Błąd”, „Uwaga” lub „Brak danych”, aby sprawdzić szczegóły.</p> : data ? <p>Brak zgłoszonych problemów. Sprawdź tempo pracy i środki poniżej.</p> : null}
        {actions.length > 1 && <details className="sc-command-more-actions"><summary>Pozostałe działania ({actions.length - 1})</summary><ul className="sc-command-actions">{actions.slice(1).map((action, i) => <li key={`${action.title}-${i}`}><b>{action.title}</b><span>{action.detail}</span></li>)}</ul></details>}
      </section>
      <div className="sc-command-toolbar"><p>Stan: {data ? date(data.generated_at) : 'brak danych'}<span>Europe/Warsaw · co 60 s</span></p><button type="button" className="sc-command-filter" aria-pressed={onlyProblems} onClick={() => setOnlyProblems(current => !current)}>Tylko problemy {onlyProblems ? '✓' : ''}</button></div>
      {data && <>
        <AgentsPanel />
        {!onlyProblems && <><section className="sc-command-kpis" aria-label="Dziś w porównaniu z wczoraj">{(data.kpis || []).map(kpi => <article key={kpi.key}><h2>{kpi.label}</h2><strong>{number(kpi.today, kpi.unit)}</strong><span className="sc-command-eyebrow">Dziś{kpi.unit ? ' · szacunek' : ''}</span><Trend {...kpi} /></article>)}</section>
          <section className="sc-command-charts" aria-label="Trendy siedmiodniowe">{(data.series || []).map(series => <Sparkline key={series.key} series={series} />)}</section></>}
        <section id="command-wallets" className="sc-command-wallets" aria-labelledby="command-wallets-title"><div className="sc-command-section-heading"><h2 id="command-wallets-title">Portfele</h2><span>X · Gemini · Anthropic</span></div><p className="sc-command-note">Tylko płatne portfele (reszta modeli działa na darmowych pulach). Dostawcy nie udostępniają salda w API: liczymy wpisane saldo minus zapisane wydatki i przeliczamy przy każdym odświeżeniu panelu (co 60 s). Brak środków (402) wykrywamy automatycznie z odpowiedzi dostawcy.</p>
          <div className="sc-command-wallet-grid">{wallets.map(wallet => <WalletCard key={wallet.provider} wallet={wallet} />)}</div>{!wallets.length && <p className="sc-command-note">{onlyProblems ? 'Brak portfeli wymagających uwagi.' : 'Brak portfeli z saldem — wpisz saldo poniżej.'}</p>}<WalletForm onSaved={refresh} />
        </section>
        <section aria-labelledby="command-details-title"><div className="sc-command-section-heading"><h2 id="command-details-title">Pełny obraz projektu</h2><span>{sections.length} sekcji · rozwiń szczegóły</span></div>
          <div className="sc-command-grid">{sections.map(section => <DetailCard key={`${section.title}-${onlyProblems}`} card={section} onlyProblems={onlyProblems} />)}</div>{onlyProblems && !sections.length && <p className="sc-command-note">Brak sekcji wymagających uwagi.</p>}
        </section>
      </>}
    </>}
    <p className="sc-command-install">Na telefonie: menu przeglądarki → Dodaj do ekranu głównego. Na iPhonie: Safari → Udostępnij → Do ekranu początkowego. Panel wymaga połączenia z internetem.</p>
  </div>;
}
