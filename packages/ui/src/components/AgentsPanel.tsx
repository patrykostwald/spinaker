'use client';

import { useEffect, useState } from 'react';
import { apiWrite } from '../lib/api';

type Note = { id: number; kind: string; track: string; title: string; body: string; status: string;
  score: number; cost_usd: string | null; created_at: string; decided_at: string | null;
  sources: { url: string; title: string }[]; critiques: { model: string; company: string; score: number; reason: string }[] };
const kinds: Record<string, string> = { signal: 'Sygnały', idea: 'Pomysły', finding: 'Znaleziska', experiment: 'Eksperymenty', request: 'Prośby', report: 'Raporty' };
const statuses: Record<string, string> = { new: 'Nowy', accepted: 'Przyjęty', rejected: 'Odrzucony', done: 'Zakończony', pending: 'Czeka na zgodę', approved: 'Zgoda zapisana', denied: 'Odmowa' };

export function AgentsPanel() {
  const [agent, setAgent] = useState('strateg');
  const [kind, setKind] = useState('');
  const [offset, setOffset] = useState(0);
  const [notes, setNotes] = useState<Note[]>([]);
  const [more, setMore] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true); setError(''); setNotes([]);
    const timeout = setTimeout(() => controller.abort(), 15000);
    void fetch(`/api/staff/agents/?agent=${agent}&kind=${kind}&offset=${offset}`, {
      credentials: 'include', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-Frontend-Domain': process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic' },
    }).then(async response => {
      if (!response.ok) throw new Error(response.status === 403 ? 'Dostęp tylko dla personelu.' : 'Nie udało się pobrać dziennika.');
      const data = await response.json();
      if (!controller.signal.aborted) { setNotes(data.results); setMore(data.has_more); }
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
  return <section className="sc-command-agents" aria-labelledby="agents-heading">
    <h2 id="agents-heading">Agenci</h2>
    <p>Strateg rozwija serwis. Dziennik Pielgrzyma zbiera propozycje dla Konsylium. Zgoda na koszt zapisuje decyzję; wykonanie wymaga kolejnego etapu.</p>
    <div className="sc-command-toolbar"><div role="group" aria-label="Wybór agenta">
      {['strateg', 'pielgrzym'].map(name => <button className="sc-command-filter" type="button" key={name} aria-pressed={agent === name}
        onClick={() => { setAgent(name); setOffset(0); }}>{name === 'strateg' ? 'Strateg' : 'Pielgrzym'}</button>)}
    </div><label>Rodzaj <select value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}>
      <option value="">Wszystkie</option>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label><button className="sc-command-refresh" type="button" disabled={loading} onClick={() => setRevision(v => v + 1)}>Odśwież dziennik</button></div>
    {error && <p role="alert" className="sc-command-error">{error}</p>}
    {loading ? <p role="status">Pobieranie dziennika…</p> : notes.length === 0 && !error ? <p>Brak wpisów dla wybranego filtra.</p> : notes.map(note => <article key={note.id} className="sc-command-card">
      <div className="sc-command-card-body"><h3>{note.title}</h3>
        <p>{kinds[note.kind]} · {statuses[note.status]}{note.track && ` · Ścieżka ${note.track}`} · {note.score}/100</p>
        <p className="sc-command-time">{new Date(note.created_at).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw' })}</p>
        {note.cost_usd !== null && <p><strong>Wnioskowany koszt: {note.cost_usd} USD</strong></p>}
        <details><summary>Treść i oceny</summary><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{note.body}</p>
          {note.critiques.map((c, i) => <p key={i}><strong>{c.company} · {c.model} · {c.score}/100</strong><br />{c.reason}</p>)}
          <ul>{note.sources.filter(s => /^https?:\/\//i.test(s.url)).map((s, i) => <li key={i}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a></li>)}</ul>
        </details>
        {note.kind === 'request' && note.status === 'pending' && <div>
          <button className="sc-command-refresh" disabled={saving !== null} onClick={() => void decide(note, 'approved')}>Zgoda</button>{' '}
          <button className="sc-command-filter" disabled={saving !== null} onClick={() => void decide(note, 'denied')}>Odmowa</button></div>}
        {['idea', 'experiment'].includes(note.kind) && note.status === 'new' && <div>
          <button className="sc-command-refresh" disabled={saving !== null} onClick={() => void decide(note, 'accepted')}>Biorę</button>{' '}
          <button className="sc-command-filter" disabled={saving !== null} onClick={() => void decide(note, 'rejected')}>Odrzucam</button></div>}
      </div></article>)}
    <div className="sc-command-toolbar"><button type="button" disabled={loading || offset === 0} onClick={() => setOffset(v => Math.max(0, v - 50))}>Nowsze</button>
      <button type="button" disabled={loading || !more} onClick={() => setOffset(v => v + 50)}>Starsze</button></div>
  </section>;
}
