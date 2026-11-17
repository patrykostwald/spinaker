"use client";
import { useEffect, useState } from 'react';
import './podmiot-nip.css';

/**
 * Podmiot po NIP (news/przeszlosc_podmiot_nip.py): zamówienia (BZP jako zamawiający, TED jako wykonawca) i dotacje UE (FTS po VAT)
 * powiązane WYŁĄCZNIE po numerze NIP. Nazwa i miejscowość pochodzą z ogłoszeń BZP tego NIP-u. Brak danych znaczy „brak w naszych danych”.
 */
type Row = { id: string; source: string; title: string; party?: string; amount: number | null; currency: string; date: string | null; kind?: string; url: string;
  amount_suspect?: boolean; programme?: string };
type Branch = { count: number; sums: { currency: string; total: number }[]; results: Row[]; suspect_count?: number };
type Data = { nip: string; status: 'found' | 'empty' | 'krs'; name: string; city?: string; province?: string; note: string; krs_number?: string; url?: string;
  contracts?: Branch; grants?: Branch; sources?: { key: string; label: string; url: string }[]; rules?: string };
const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : 'brak daty';
const money = (v: number, c: string) => `${v.toLocaleString('pl-PL', { maximumFractionDigits: 0 })} ${c === 'PLN' ? 'zł' : c}`;
const SRC: Record<string, string> = { bzp: 'BZP', ted: 'TED', fts: 'FTS', niw: 'NIW' };

function List({ title, data, empty }: { title: string; data: Branch; empty: string }) {
  return <section className="px-card px-pn__card" aria-label={title}>
    <h2 className="px-h3">{title} <small>{data.count}</small></h2>
    {data.sums.length > 0 && <p className="px-pn__sum">{data.sums.map(s => money(s.total, s.currency)).join(' + ')} <small>kwoty z ogłoszeń, bez pozycji wątpliwych</small></p>}
    {data.count === 0 ? <p className="px-note">{empty}</p> : <ul className="px-pn__list">{data.results.map(r => <li key={r.id}>
      <a href={r.url} target="_blank" rel="noopener noreferrer" title={r.title}>
        <b>{r.title || 'bez tytułu'}</b>
        <span className="px-pn__val">{r.amount !== null && r.amount !== undefined ? money(r.amount, r.currency) : day(r.date)}</span>
        <small>{[SRC[r.source] ?? r.source, r.amount !== null && r.amount !== undefined ? day(r.date) : '', r.party, r.programme, r.amount_suspect ? 'kwota wątpliwa (poza sumą)' : ''].filter(Boolean).join(' · ')} ↗</small>
      </a></li>)}</ul>}
    {data.count > data.results.length && <p className="px-card__foot">{`Pokazujemy ${data.results.length} z ${data.count} pozycji.`}</p>}
  </section>;
}

export function PodmiotNip({ nip }: { nip: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch(`/api/przeszlosc/podmiot/${nip}/`).then(r => r.ok ? r.json() : Promise.reject(r.status)).then((d: Data) => { if (live) setData(d); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [nip]);
  return <section className="px-sec px-pn" aria-labelledby="pn-h">
    <div className="pt-head__l"><p className="px-kicker">Podmiot po numerze NIP</p>
      <h1 id="pn-h">{data?.name || `NIP ${nip}`}</h1></div>
    <p className="px-pn__sub">{[`NIP ${nip}`, data?.city, data?.province].filter(Boolean).join(' · ')}</p>
    {failed && <p className="px-msg" role="alert">Nie udało się pobrać danych. Spróbuj ponownie za chwilę.</p>}
    {data && <p className="px-note px-pn__note">{data.note}</p>}
    {data?.status === 'krs' && data.url && <p><a className="px-link" href={data.url}>Pełna strona podmiotu (KRS {data.krs_number}) →</a></p>}
    {data?.status === 'found' && data.contracts && data.grants && <>
      <List title="Zamówienia publiczne" data={data.contracts} empty="Brak ogłoszeń w naszych danych." />
      <List title="Dotacje UE (FTS)" data={data.grants} empty="Brak dotacji powiązanych po NIP w naszych danych." />
      <p className="px-note">{data.rules} Źródła: {data.sources?.map((s, i) => <span key={s.key}>{i ? ', ' : ''}<a className="px-link" href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a></span>)}.</p>
    </>}
  </section>;
}
