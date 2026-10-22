"use client";

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { getClinicDeleted, getClinicMessages, searchClinicSpins } from '../../lib/clinic';

type Item = { key: string; time: string; text: string; href: string; tone?: 'lo' | 'mid' | 'hi'; value?: string };

const hour = (iso?: string) => iso ? new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }) : '';
const tone = (n: number): Item['tone'] => n >= 70 ? 'hi' : n >= 40 ? 'mid' : 'lo';

/** Na przemian rządzący i opozycja: ta sama miara, nigdy kilka pozycji jednej strony z rzędu. */
function alternate<T extends { camp?: string }>(rows: T[]) {
  const gov = rows.filter(r => r.camp === 'government'), opp = rows.filter(r => r.camp !== 'government');
  const out: T[] = [];
  for (let i = 0; i < Math.max(gov.length, opp.length); i++) { if (gov[i]) out.push(gov[i]); if (opp[i]) out.push(opp[i]); }
  return out;
}

/**
 * Pasek „co się dziś wydarzyło w danych” (właściciel 4.10): tylko własne, sprawdzone dane spin.clinic, w naszym stylu
 * (bez wypełnienia, cienka linia, szarości; kolor tylko przy sile spinu). Przewija się wolno, staje po najechaniu,
 * przy ograniczonym ruchu stoi.
 */
const wpisy = (n: number) => `${n} ${n === 1 ? 'wpis' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'wpisy' : 'wpisów'}`;
export function HomeTicker() {
  const spins = useQuery({ queryKey: ['ticker', 'spins'], queryFn: () => searchClinicSpins({ sort: 'new' }), staleTime: 300_000, retry: false });
  const messages = useQuery({ queryKey: ['ticker', 'messages'], queryFn: () => getClinicMessages(1), staleTime: 600_000, retry: false });
  const deleted = useQuery({ queryKey: ['ticker', 'deleted'], queryFn: getClinicDeleted, staleTime: 600_000, retry: false });

  const items: Item[] = [];
  const seen = new Set<string>();
  alternate((spins.data?.results ?? []).filter(s => !seen.has(s.author.name) && seen.add(s.author.name)).slice(0, 8)).forEach(s => items.push({ key: `s${s.id}`, time: hour(s.post?.published_at),
    text: `${s.author.name} · siła spinu`, value: `${s.intensity}/100`, tone: tone(s.intensity), href: `/klinika/${s.id}` }));
  const day = messages.data?.results?.[0];
  if (day) {
    const part = (label: string, m: typeof day.government) => m ? `${label}: ${wpisy(m.posts_count)}${m.themes?.[0] ? `, temat: ${m.themes[0]}` : ''}` : '';
    const text = [part('Rządzący', day.government), part('Opozycja', day.opposition)].filter(Boolean).join(' · ');
    if (text) items.splice(Math.min(2, items.length), 0, { key: `m${day.day}`, time: 'przekaz dnia', text, href: `/klinika/przekazy/${day.day}` });
  }
  (deleted.data?.items ?? []).slice(0, 2).forEach((d, i) => items.splice(Math.min(4 + i * 3, items.length), 0, { key: `d${i}${d.published_at}`,
    time: hour(d.unavailable_at), text: `${d.author.name}: wpis niedostępny po ${Math.max(1, Math.round(d.hours_visible))} godz.`, href: '/klinika#niedostepne' }));
  if (items.length < 3) return null;

  const row = (copy: number) => <ul className="sc-ticker__row" aria-hidden={copy > 0 || undefined}>{items.map(item =>
    <li key={`${copy}-${item.key}`}><Link href={item.href} tabIndex={copy ? -1 : undefined}><time>{item.time}</time>{item.text}{item.value && <b data-tone={item.tone}> {item.value}</b>}</Link></li>)}</ul>;
  return <section className="sc-ticker" aria-label="Dziś w danych spin.clinic">
    <div className="sc-ticker__track" style={{ ['--n' as string]: items.length }}>{row(0)}{row(1)}</div>
  </section>;
}
