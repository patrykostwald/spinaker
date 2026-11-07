"use client";
import { useEffect, useState } from 'react';
import './finanse-partii.css';

/**
 * Finanse partii i komitetów (PKW): spis dokumentów z pkw.gov.pl + streszczenie uchwał PKW o sprawozdaniach partii
 * (news/przeszlosc_pkw.py, scraper/public_record_parsers.py::pkw_report). Kwoty tylko z tekstu uchwały, z cytatem; skanów nie czytamy (bez OCR);
 * zawsze odnośnik do oryginału. Nie ma tu nazwisk darczyńców ani numerów rachunków.
 */
type Amount = { key: string; label: string; value: string; currency: string; quote: string };
type Report = { readable: boolean; reason?: string; resolution?: string; resolution_date?: string; year?: number; name?: string;
  decision?: 'przyjete' | 'odrzucone' | 'bez_rozpatrzenia' | null; with_irregularity?: boolean; amounts?: Amount[] } | null;
type Row = { title: string; kind: string; published: string | null; url: string; report: Report };
type Kind = { key: string; label: string; count: number };
type Data = { total: number; all: number; with_data: number; page: number; pages: number; kinds: Kind[]; results: Row[]; note: string; source: { label: string; url: string } };
const API = '/api/przeszlosc/pkw/';
const PER = 20;
const DECISION: Record<string, string> = { przyjete: 'sprawozdanie przyjęte', odrzucone: 'sprawozdanie odrzucone', bez_rozpatrzenia: 'pozostawione bez rozpatrzenia' };
const money = (v: string, c: string) => `${Number(v).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${c === 'PLN' ? 'zł' : c}`;
const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : 'brak daty';

export function FinansePartii() {
  const [draft, setDraft] = useState('');
  const [q, setQ] = useState('');
  const [kind, setKind] = useState('');
  const [withData, setWithData] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Data | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [failed, setFailed] = useState(false);
  useEffect(() => { setPage(1); }, [q, kind, withData]);
  useEffect(() => {
    let live = true;
    const p = new URLSearchParams({ strona: String(page), na_strone: String(PER) });
    if (q) p.set('q', q);
    if (kind) p.set('rodzaj', kind);
    if (withData) p.set('z_danymi', '1');
    fetch(`${API}?${p}`).then(r => r.ok ? r.json() : Promise.reject(r.status)).then((d: Data) => {
      if (!live) return; setData(d); setFailed(false); setRows(prev => page > 1 ? [...prev, ...d.results] : d.results);
    }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [q, kind, withData, page]);
  return <section className="px-sec px-fp" aria-labelledby="fp-h">
    <div className="pt-head__l"><p className="px-kicker">Finanse polityki</p><h1 id="fp-h">Finanse partii i komitetów</h1></div>
    <p className="px-fp__lead">Spis sprawozdań z pkw.gov.pl. Przy uchwałach PKW o sprawozdaniach partii pokazujemy decyzję i kwoty odczytane z tekstu uchwały, z cytatem. Oryginał zawsze jest o jedno kliknięcie dalej.</p>
    <form className="px-fp__find" role="search" onSubmit={e => { e.preventDefault(); setQ(draft.trim()); }}>
      <label htmlFor="fp-q">Nazwa partii lub komitetu</label>
      <input id="fp-q" type="search" value={draft} maxLength={120} placeholder="np. Lewica, Piratów, Konfederacja" onChange={e => setDraft(e.target.value)} />
      <button type="submit" className="px-btn">Szukaj</button>
    </form>
    <div className="px-fp__filters" role="group" aria-label="Filtry">
      <div className="px-chips" role="group" aria-label="Rodzaj dokumentu">
        <button type="button" aria-pressed={!kind} onClick={() => setKind('')}>Wszystkie</button>
        {data?.kinds.map(k => <button key={k.key} type="button" aria-pressed={kind === k.key} onClick={() => setKind(k.key)}>{`${k.label} (${k.count})`}</button>)}
      </div>
      <label className="px-fp__check"><input type="checkbox" checked={withData} onChange={e => setWithData(e.target.checked)} />
        Tylko z odczytanymi kwotami{data ? ` (${data.with_data})` : ''}</label>
    </div>
    {failed && <p className="px-msg" role="alert">Nie udało się pobrać spisu. Spróbuj ponownie za chwilę.</p>}
    {data && <p className="px-note" role="status">{data.total.toLocaleString('pl-PL')} z {data.all.toLocaleString('pl-PL')} dokumentów</p>}
    <ul className="px-fp__list">{rows.map(r => <li key={r.url} className="px-card px-fp__item">
      <h2 className="px-h3">{r.title}</h2>
      <p className="px-fp__meta">{data?.kinds.find(k => k.key === r.kind)?.label ?? r.kind} · na stronie PKW od {day(r.published)}</p>
      {r.report?.readable && <div className="px-fp__report">
        <p><b>{r.report.name}</b>, sprawozdanie za {r.report.year}: {DECISION[r.report.decision ?? ''] ?? 'decyzja nieodczytana'}
          {r.report.with_irregularity ? ' ze wskazaniem uchybienia' : ''}. Uchwała PKW nr {r.report.resolution} z {day(r.report.resolution_date)}.</p>
        {(r.report.amounts?.length ?? 0) > 0 && <dl className="px-fp__amounts">{r.report.amounts!.map(a => <div key={a.key} title={a.quote ? `Z uchwały: „${a.quote}”` : undefined}>
          <dt>{a.label}</dt><dd>{money(a.value, a.currency)}</dd></div>)}</dl>}
      </div>}
      {r.report && !r.report.readable && <p className="px-fp__unread">Nie odczytujemy kwot z tego pliku: {r.report.reason}.</p>}
      <p className="px-card__foot"><a className="px-link" href={r.url} target="_blank" rel="noopener noreferrer">Oryginał (PDF) na pkw.gov.pl ↗</a></p>
    </li>)}</ul>
    {data && data.page < data.pages && <button type="button" className="px-more" onClick={() => setPage(p => p + 1)}>{`Pokaż więcej (${data.total - rows.length})`}</button>}
    {data && <p className="px-note">{data.note} Źródło: <a className="px-link" href={data.source.url} target="_blank" rel="noopener noreferrer">{data.source.label} ↗</a></p>}
  </section>;
}
