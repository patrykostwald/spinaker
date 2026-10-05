'use client';

import { useEffect, useState } from 'react';
import { apiWrite } from '../lib/api';

type Note = { id: number; kind: string; track: string; title: string; body: string; status: string;
  score: number; cost_usd: string | null; created_at: string; decided_at: string | null;
  sources: { url: string; title: string }[]; critiques: { model: string; company: string; score: number; reason: string;
    role?: string; verdict?: string; round?: number; failure?: string; cost?: string; legal_reputation?: string; bias?: string; duplicates?: string }[] };
type WardenItem = { id: number; handle: string; status: string; reason: string; first_decision: string; second_decision: string;
  evidence: { old_name?: string; new_name?: string; expected_name?: string }; second_evidence: unknown;
  created_at: string; due_at: string; last_error: string; seba: { reason: string }[]; seba_waiting: boolean };
const kinds: Record<string, string> = { signal: 'Sygnały', idea: 'Pomysły', finding: 'Znaleziska', experiment: 'Eksperymenty', request: 'Prośby', report: 'Raporty' };
const statuses: Record<string, string> = { new: 'Nowy', accepted: 'Przyjęty', rejected: 'Odrzucony', done: 'Zakończony', pending: 'Czeka na zgodę', approved: 'Zgoda zapisana', denied: 'Odmowa' };

type AgentRow = { id: string; name: string; description: string; collector: boolean; flag: string;
  enabled: boolean; schedule: string; last_run: string | null; next_run: string | null;
  result: 'ok' | 'warn' | 'error'; summary: string; cost_today_usd: number | null; cost_note: string; source: string };
// „dziś 14:15”, „wczoraj 21:45”, „jutro 03:10”, inaczej „5.10 07:00” (czas warszawski).
const when = (value: string | null) => {
  if (!value) return 'brak';
  const zone = { timeZone: 'Europe/Warsaw' } as const;
  const date = new Date(value);
  const day = (d: Date) => d.toLocaleDateString('pl-PL', zone);
  const hour = date.toLocaleTimeString('pl-PL', { ...zone, hour: '2-digit', minute: '2-digit' });
  const shift = (n: number) => day(new Date(Date.now() + n * 86400000));
  const label = day(date) === shift(0) ? 'dziś' : day(date) === shift(-1) ? 'wczoraj' : day(date) === shift(1) ? 'jutro'
    : date.toLocaleDateString('pl-PL', { ...zone, day: 'numeric', month: 'numeric' });
  return `${label} ${hour}`;
};
const RESULT: Record<string, string> = { ok: 'OK', warn: 'Uwaga', error: 'Błąd', off: 'Wyłączony' };
const state = (row: AgentRow) => (row.enabled ? row.result : 'off');
const ORDER: Record<string, number> = { error: 0, warn: 1, ok: 2, off: 3 };

function AgentRowView({ row }: { row: AgentRow }) {
  const s = state(row);
  return <details className="sc-agentmap__row" data-status={s}>
    <summary>
      <span className="sc-agentmap__dot" aria-label={RESULT[s]} />
      <span className="sc-agentmap__name"><strong>{row.name}</strong><small>{row.description}</small></span>
      <span className="sc-agentmap__when"><small>ostatnio</small>{when(row.last_run)}</span>
      <span className="sc-agentmap__sched">{row.schedule}</span>
    </summary>
    <dl className="sc-agentmap__more">
      <div><dt>Wynik</dt><dd><b data-status={s}>{RESULT[s]}</b> {row.summary}</dd></div>
      <div><dt>Następny bieg</dt><dd>{row.enabled ? when(row.next_run) : 'wyłączony'}</dd></div>
      {row.cost_today_usd != null && <div><dt>Koszt dziś</dt><dd title={row.cost_note}>{row.cost_today_usd.toLocaleString('pl-PL', { maximumFractionDigits: 3 })} USD</dd></div>}
      {row.flag && <div><dt>Włącznik</dt><dd><code>{row.flag}</code> {row.enabled ? 'włączony' : 'wyłączony'}</dd></div>}
      {row.source && <div><dt>Zadanie</dt><dd>{row.source}</dd></div>}
    </dl>
  </details>;
}

// Kategorie mapy (właściciel 5.10: kafelki z ikoną, 2-4 w rzędzie, pogrupowane)
const CATEGORIES: { id: string; label: string; icon: string; ids: string[] }[] = [
  { id: 'tresc', label: 'Treść serwisu', icon: 'M7 3h7l4 4v14H7zM14 3v4h4M10 12h6M10 16h6',
    ids: ['dr-spin', 'screen', 'plain-editor', 'plain-meter', 'plain-guard', 'plain-reader', 'messages', 'interviews', 'interview-pick', 'interview-candidates', 'spin-thread', 'narrative-threads', 'signal-threads', 'weekly', 'raportysta', 'council'] },
  { id: 'straz', label: 'Strażnicy', icon: 'M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4',
    ids: ['recenzent', 'thread-review', 'inquisitor', 'auditor', 'warden', 'second-key', 'seba', 'krs'] },
  { id: 'nieza', label: 'Niezawodność i dyrygent', icon: 'M3 12h4l2-5 4 10 2-5h6',
    ids: ['dyrygent', 'automatyk', 'opiekunowie', 'duty', 'repairer', 'mechanik', 'schedule-health', 'video-stats'] },
  { id: 'rozwoj', label: 'Rozwój i nauka', icon: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6',
    ids: ['strateg', 'pilgrim', 'reports', 'ekspert-ai', 'recruiter', 'projektant', 'badacz'] },
  { id: 'osint', label: 'przeszłość.today', icon: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
    ids: ['pracownia-osint', 'przeszlosc-topics'] },
  { id: 'pub', label: 'Publikacja i czytelnicy', icon: 'M4 10v4h3l6 4V6L7 10zM16 9a4 4 0 0 1 0 6M18.5 7a7 7 0 0 1 0 10',
    ids: ['x-publish', 'social', 'social-assistant', 'push', 'notifications', 'digests', 'moderation-mail'] },
];
const COLLECT_ICON = 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6';
const identity = (row: AgentRow) => row.id.slice(0, row.id.lastIndexOf(':'));
const Icon = ({ d }: { d: string }) => <svg viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;

function AgentTile({ row, icon, selected, onSelect }: { row: AgentRow; icon: string; selected: boolean; onSelect: () => void }) {
  const s = state(row);
  return <button type="button" className="sc-agenttile" data-status={s} aria-pressed={selected} onClick={onSelect} title={row.description}>
    <span className="sc-agenttile__icon"><Icon d={icon} /><i aria-label={RESULT[s]} /></span>
    <strong>{row.name}</strong>
    <small>{row.description}</small>
    <span className="sc-agenttile__foot"><span>{when(row.last_run)}</span><span>{row.schedule}</span></span>
  </button>;
}

function AgentDetail({ row, onClose }: { row: AgentRow; onClose: () => void }) {
  const s = state(row);
  return <div className="sc-agentdetail" data-status={s}>
    <header><strong>{row.name}</strong><b data-status={s}>{RESULT[s]}</b><button type="button" onClick={onClose} aria-label="Zamknij szczegóły">✕</button></header>
    <p>{row.description}</p>
    <dl className="sc-agentmap__more">
      <div><dt>Wynik</dt><dd>{row.summary}</dd></div>
      <div><dt>Ostatnio</dt><dd>{when(row.last_run)}</dd></div>
      <div><dt>Następny bieg</dt><dd>{row.enabled ? when(row.next_run) : 'wyłączony'}</dd></div>
      <div><dt>Harmonogram</dt><dd>{row.schedule}</dd></div>
      {row.cost_today_usd != null && <div><dt>Koszt dziś</dt><dd title={row.cost_note}>{row.cost_today_usd.toLocaleString('pl-PL', { maximumFractionDigits: 3 })} USD</dd></div>}
      {row.flag && <div><dt>Włącznik</dt><dd><code>{row.flag}</code> {row.enabled ? 'włączony' : 'wyłączony'}</dd></div>}
      {row.source && <div><dt>Zadanie</dt><dd>{row.source}</dd></div>}
    </dl>
  </div>;
}

function TileGroup({ label, icon, rows, selected, setSelected }: { label: string; icon: string; rows: AgentRow[]; selected: string | null; setSelected: (id: string | null) => void }) {
  if (!rows.length) return null;
  const bad = rows.filter(r => state(r) === 'error').length, warn = rows.filter(r => state(r) === 'warn').length;
  const open = rows.find(r => r.id === selected);
  return <section className="sc-agentgroup" aria-label={label}>
    <h3><Icon d={icon} />{label}<span>{rows.length}</span>{bad > 0 && <em data-status="error">{bad} błąd</em>}{warn > 0 && <em data-status="warn">{warn} uwagi</em>}</h3>
    <div className="sc-agentgrid">{rows.map(row => <AgentTile key={row.id} row={row} icon={icon} selected={row.id === selected}
      onSelect={() => setSelected(row.id === selected ? null : row.id)} />)}</div>
    {open && <AgentDetail row={open} onClose={() => setSelected(null)} />}
  </section>;
}

function AgentMap() {
  const [rows, setRows] = useState<AgentRow[]>([]);
  const [reports, setReports] = useState<Note[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true); setError('');
    const timeout = setTimeout(() => controller.abort(), 15000);
    void fetch('/api/staff/agents/map/', { credentials: 'include', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
    }).then(async response => {
      if (!response.ok) throw new Error('Nie udało się pobrać mapy agentów.');
      const data = await response.json();
      if (active) { setRows(data.results); setReports(data.reports); }
    }).catch(e => { if (active) setError(controller.signal.aborted ? 'Przekroczono czas pobierania mapy.' : e.message); })
      .finally(() => { clearTimeout(timeout); if (active) setLoading(false); });
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [revision]);
  const sorted = (items: AgentRow[]) => [...items].sort((a, b) => ORDER[state(a)] - ORDER[state(b)] || a.name.localeCompare(b.name, 'pl'));
  // jeden kafelek na agenta: kilka harmonogramów tego samego agenta scalamy (gorszy wynik, wszystkie godziny)
  const merge = (items: AgentRow[]) => Object.values(items.reduce<Record<string, AgentRow>>((acc, row) => {
    const key = identity(row), prev = acc[key];
    if (!prev) acc[key] = { ...row };
    else acc[key] = { ...(ORDER[state(row)] < ORDER[state(prev)] ? row : prev), id: prev.id, schedule: `${prev.schedule} · ${row.schedule}`,
      last_run: [prev.last_run, row.last_run].filter(Boolean).sort().pop() ?? null };
    return acc;
  }, {}));
  const agents = sorted(merge(rows.filter(row => !row.collector)));
  const collectors = sorted(merge(rows.filter(row => row.collector)));
  const count = (s: string) => agents.filter(row => state(row) === s).length;
  const problems = count('error') + count('warn');
  return <details className="sc-agentmap" open={problems > 0 || undefined}>
    <summary className="sc-agentmap__head">
      <span><strong>Mapa agentów</strong><small>co robią, kiedy działają, z jakim wynikiem · kliknij kafelek po szczegóły</small></span>
      <span className="sc-agentmap__chips">
        {loading ? <em>wczytywanie…</em> : <>
          <em data-status="ok">{count('ok')} OK</em>
          {count('warn') > 0 && <em data-status="warn">{count('warn')} uwagi</em>}
          {count('error') > 0 && <em data-status="error">{count('error')} błąd</em>}
          {count('off') > 0 && <em data-status="off">{count('off')} wyłączone</em>}
        </>}
      </span>
    </summary>
    <div className="sc-agentmap__body">
      <div className="sc-agentmap__tools"><button type="button" className="sc-command-refresh" disabled={loading} onClick={() => setRevision(v => v + 1)}>Odśwież</button></div>
      {error && <p role="alert" className="sc-command-error">{error}</p>}
      {CATEGORIES.map(c => <TileGroup key={c.id} label={c.label} icon={c.icon} selected={selected} setSelected={setSelected}
        rows={agents.filter(row => c.ids.includes(identity(row)))} />)}
      <TileGroup label="Pozostali" icon="M5 12h14M12 5v14" selected={selected} setSelected={setSelected}
        rows={agents.filter(row => !CATEGORIES.some(c => c.ids.includes(identity(row))))} />
      {collectors.length > 0 && <details className="sc-agentmap__group"><summary>Zbieracze danych ({collectors.length})</summary>
        <TileGroup label="Zbieracze danych" icon={COLLECT_ICON} rows={collectors} selected={selected} setSelected={setSelected} /></details>}
      {reports.length > 0 && <details className="sc-agentmap__group"><summary>Ostatnie raporty agentów ({reports.length})</summary>
        <div className="sc-agentmap__list">{reports.map(note => <details key={note.id} className="sc-agentmap__row" data-status="ok">
          <summary><span className="sc-agentmap__dot" /><span className="sc-agentmap__name"><strong>{note.title}</strong></span><span className="sc-agentmap__when">{when(note.created_at)}</span></summary>
          <p className="sc-agentmap__report">{note.body}</p></details>)}</div></details>}
    </div>
  </details>;
}

export function AgentsPanel() {
  const [agent, setAgent] = useState('strateg');
  const [kind, setKind] = useState('');
  const [offset, setOffset] = useState(0);
  const [notes, setNotes] = useState<Note[]>([]);
  const [rejected, setRejected] = useState<Note[]>([]);
  const [queued, setQueued] = useState(0);
  const [reviews, setReviews] = useState<WardenItem[]>([]);
  const [more, setMore] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true); setError(''); setNotes([]); setRejected([]); setReviews([]); setQueued(0);
    const timeout = setTimeout(() => controller.abort(), 15000);
    void fetch(agent === 'warden' ? `/api/staff/warden-reviews/?offset=${offset}` : `/api/staff/agents/?agent=${agent}&kind=${kind}&offset=${offset}`, {
      credentials: 'include', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
    }).then(async response => {
      if (!response.ok) throw new Error(response.status === 403 ? 'Dostęp tylko dla personelu.' : 'Nie udało się pobrać dziennika.');
      const data = await response.json();
      if (!controller.signal.aborted) {
        if (agent === 'warden') setReviews(data.results);
        else { setNotes(data.results); setRejected(data.rejected || []); setQueued(data.seba_queued || 0); }
        setMore(data.has_more);
      }
    }).catch(e => { if (active) setError(controller.signal.aborted ? 'Przekroczono czas pobierania dziennika.' : e.message); })
      .finally(() => { clearTimeout(timeout); if (active) setLoading(false); });
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [agent, kind, offset, revision]);
  const decide = async (note: Note, decision: string) => {
    setSaving(note.id); setError('');
    try {
      await apiWrite(`/api/staff/agents/${note.id}/decision/`, { decision });
      setRevision(v => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać decyzji.'); }
    finally { setSaving(null); }
  };
  const decideWarden = async (item: WardenItem, decision: string) => {
    setSaving(item.id); setError('');
    try {
      await apiWrite(`/api/staff/warden-reviews/${item.id}/decision/`, { decision });
      setRevision(v => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać decyzji.'); }
    finally { setSaving(null); }
  };
  return <section className="sc-command-agents" aria-labelledby="agents-heading">
    <h2 id="agents-heading">Agenci</h2>
    <p><a href="/admin/news/institutionalreport/">Raportysta: raporty, recenzje i pliki do zatwierdzenia</a></p>
    <AgentMap />
    <p>Strateg rozwija serwis. Pielgrzym zbiera propozycje dla Konsylium. Ekspert AI raz w tygodniu pisze stan wiedzy o AI (tylko ze źródłami) i wskazuje Rekruterowi modele do egzaminu. Seba sprawdza pomysły przed Twoją decyzją. Drugi klucz weryfikuje wnioski Strażnika kont.</p>
    <div className="sc-command-toolbar"><div role="group" aria-label="Wybór agenta">
      {['strateg', 'pielgrzym', 'ekspert', 'recenzent', 'projektant', 'warden'].map(name => <button className="sc-command-filter" type="button" key={name} aria-pressed={agent === name}
        onClick={() => { setAgent(name); setOffset(0); }}>{name === 'strateg' ? 'Strateg' : name === 'warden' ? 'Drugi klucz' : name === 'ekspert' ? 'Ekspert AI' : name === 'recenzent' ? 'Recenzent' : name === 'projektant' ? 'Projektant UX/UI' : 'Pielgrzym'}</button>)}
    </div><label>Rodzaj <select disabled={agent === 'warden'} value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}>
      <option value="">Wszystkie</option>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label><button className="sc-command-refresh" type="button" disabled={loading} onClick={() => setRevision(v => v + 1)}>Odśwież dziennik</button></div>
    {error && <p role="alert" className="sc-command-error">{error}</p>}
    {queued > 0 && <p role="status">Czeka na Sebę: {queued}. Oceny wrócą w kolejnym wolnym oknie.</p>}
    {loading ? <p role="status">Pobieranie dziennika…</p> : notes.length === 0 && reviews.length === 0 && !error ? <p>Brak wpisów dla wybranego filtra.</p> : notes.map(note => <article key={note.id} className="sc-command-card">
      <div className="sc-command-card-body"><h3>{note.title}</h3>
        <p>{kinds[note.kind]} · {statuses[note.status]}{note.track && ` · Ścieżka ${note.track}`} · {note.score}/100</p>
        <p className="sc-command-time">{new Date(note.created_at).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw' })}</p>
        {note.cost_usd !== null && <p><strong>Wnioskowany koszt: {note.cost_usd} USD</strong></p>}
        <details><summary>Treść i oceny</summary><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{note.body}</p>
          {note.critiques.map((c, i) => <div key={i}><p><strong>{c.role === 'Seba' ? `Seba, runda ${c.round} · ${c.verdict} · ` : ''}{c.company} · {c.model} · {c.score}/{c.role === 'Seba' ? 10 : 100}</strong><br />{c.reason}</p>
            {c.role === 'Seba' && <ul>{[c.failure, c.cost, c.legal_reputation, c.bias, c.duplicates].filter(Boolean).map((text, j) => <li key={j}>{text}</li>)}</ul>}</div>)}
          <ul>{note.sources.filter(s => /^https?:\/\//i.test(s.url)).map((s, i) => <li key={i}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a></li>)}</ul>
        </details>
        {note.kind === 'request' && note.status === 'pending' && <div>
          <button className="sc-command-refresh" disabled={saving !== null} onClick={() => void decide(note, 'approved')}>Zgoda</button>{' '}
          <button className="sc-command-filter" disabled={saving !== null} onClick={() => void decide(note, 'denied')}>Odmowa</button></div>}
        {['idea', 'experiment'].includes(note.kind) && note.status === 'new' && <div>
          <button className="sc-command-refresh" disabled={saving !== null} onClick={() => void decide(note, 'accepted')}>Biorę</button>{' '}
          <button className="sc-command-filter" disabled={saving !== null} onClick={() => void decide(note, 'rejected')}>Odrzucam</button></div>}
      </div></article>)}
    {rejected.length > 0 && <details><summary>Odrzucone przez Sebę ({rejected.length})</summary>
      {rejected.map(note => <article className="sc-command-card" key={note.id}><div className="sc-command-card-body"><h3>{note.title}</h3>
        {note.critiques.filter(c => c.role === 'Seba').map((c, i) => <div key={i}><p><strong>Runda {c.round}: {c.verdict}, {c.score}/10</strong><br />{c.reason}</p>
          <ul>{[c.failure, c.cost, c.legal_reputation, c.bias, c.duplicates].filter(Boolean).map((text, j) => <li key={j}>{text}</li>)}</ul></div>)}
        <details><summary>Propozycja</summary><p style={{ whiteSpace: 'pre-wrap' }}>{note.body}</p></details>
      </div></article>)}</details>}
    {reviews.map(item => <article key={item.id} className="sc-command-card"><div className="sc-command-card-body">
      <h3>{item.status === 'owner' ? 'Wymaga Ciebie' : 'Czeka na drugi klucz'}: @{item.handle}</h3><p>{item.reason}</p>
      <p>Stara nazwa: {item.evidence.old_name || 'brak'}. Nowa nazwa: {item.evidence.new_name || 'brak'}.</p>
      <p>Drugi klucz: {({ disable: 'potwierdza wyłączenie', keep: 'nie potwierdza wyłączenia', uncertain: 'brak jednoznacznych dowodów' } as Record<string, string>)[item.second_decision] || 'czeka na odczyt'}.</p>
      {item.status === 'pending' && <p>Najwcześniejsza kontrola: {new Date(item.due_at).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw' })}.</p>}
      {item.last_error && <p>{item.last_error}</p>}
      {item.seba.map((c, i) => <p key={i}><strong>Seba:</strong> {c.reason}</p>)}
      {item.seba_waiting && <p>Seba czeka na darmowe okno.</p>}
      <details><summary>Dowody obu kluczy</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ pierwszy: item.evidence, drugi: item.second_evidence }, null, 2)}</pre></details>
      {item.status === 'owner' && <div><button type="button" className="sc-command-filter" disabled={saving !== null} onClick={() => void decideWarden(item, 'disable')}>Wyłącz</button>{' '}
        <button type="button" className="sc-command-refresh" disabled={saving !== null} onClick={() => void decideWarden(item, 'keep')}>Zostaw</button></div>}
    </div></article>)}
    <div className="sc-command-toolbar"><button type="button" disabled={loading || offset === 0} onClick={() => setOffset(v => Math.max(0, v - 50))}>Nowsze</button>
      <button type="button" disabled={loading || !more} onClick={() => setOffset(v => v + 50)}>Starsze</button></div>
  </section>;
}
