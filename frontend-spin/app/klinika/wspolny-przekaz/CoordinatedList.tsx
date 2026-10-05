"use client";
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ClinicNav } from '@spin-clinic/ui';
import { Loading, SectionHeader } from '@spin-clinic/ui/kit';
import './wspolny-przekaz.css';

/**
 * Wspólny przekaz (plan Architekta 6.10): prawie identyczne zdania we wpisach co najmniej 3 kont w 6 godzin.
 * Jedna lista od najnowszego, wszystkie obozy razem i te same progi (news/coordinated.py). Bez kolorów obozów:
 * etykieta mówi tylko, czy przekaz przekracza granice partii.
 */
type Account = { handle: string; name: string; party: string | null; camp: string };
type Cluster = { id: number; phrase: string; accounts_count: number; posts_count: number; parties: string[]; camps: string[]; cross_party: boolean; cross_camp: boolean;
  first_at: string; last_at: string; span_minutes: number; accounts: Account[]; posts: { url: string; handle: string; published_at: string }[] };
type Data = { method: string; results: Cluster[] };

const ACCOUNTS_SHOWN = 4;
const when = (iso: string) => new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
const hour = (iso: string) => new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
const span = (m: number) => m < 1 ? 'w ciągu minuty' : 'w ' + (m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ''}`);
const nice = (name: string) => name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase() ? w[0] + w.slice(1).toLowerCase() : w).join('');
const plural = (n: number, one: string, few: string, many: string) => n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;

function label(c: Cluster): [string, string] {
  if (c.cross_camp) return ['camps', 'rządzący i opozycja'];
  if (c.cross_party) return ['parties', 'kilka partii'];
  if (c.parties.length === 1) return ['party', 'jedna partia'];
  return ['unknown', 'partia nieustalona'];
}

export function CoordinatedList() {
  const [data, setData] = useState<Data | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    fetch('/api/clinic/wspolny-przekaz/?limit=40').then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Data) => { setData(d); setState('ok'); }).catch(() => setState('error'));
  }, []);
  return <section className="sc-clinic sc-wp" aria-labelledby="wp-title">
    <ClinicNav />
    <SectionHeader variant="page" titleId="wp-title" title="Wspólny przekaz"
      kicker={<Link href="/klinika">Klinika spinu</Link>}
      subtitle="Prawie identyczne zdania, które co najmniej 3 różne konta polityków napisały w ciągu 6 godzin. Te same progi dla wszystkich obozów; wspólny przekaz to obserwacja, nie dowód zmowy." />
    {state === 'loading' && <p className="sc-clinic-empty"><Loading label="Ładowanie wspólnego przekazu" /></p>}
    {state === 'error' && <p className="sc-clinic-empty" role="alert">Nie udało się pobrać listy. Odśwież stronę za chwilę.</p>}
    {data && !data.results.length && <p className="sc-clinic-empty">W ostatnich dniach nie było wspólnego przekazu według tych progów.</p>}
    {data && data.results.length > 0 && <ol className="sc-wp__list">{data.results.map(c => {
      const [kind, text] = label(c);
      const rest = c.accounts.length - ACCOUNTS_SHOWN;
      return <li key={c.id} className="sc-wp__card" data-kind={kind}>
        <header className="sc-wp__head">
          <time dateTime={c.first_at}>{when(c.first_at)}{c.span_minutes > 0 ? ` - ${hour(c.last_at)}` : ''}</time>
          <span className="sc-wp__tag" data-kind={kind}>{text}</span>
        </header>
        <blockquote className="sc-wp__phrase" lang="pl" data-open={open === c.id || undefined}>„{c.phrase}”</blockquote>
        <p className="sc-wp__meta"><b>{c.accounts_count} {plural(c.accounts_count, 'konto', 'konta', 'kont')}</b>
          <span>{c.parties.length ? c.parties.join(', ') : 'bez przypisanej partii'}</span>
          <span>{span(c.span_minutes)}</span></p>
        <p className="sc-wp__who">{c.accounts.slice(0, ACCOUNTS_SHOWN).map(a => nice(a.name)).join(', ')}{rest > 0 ? ` i ${rest} ${plural(rest, 'inne', 'inne', 'innych')}` : ''}</p>
        <footer className="sc-wp__foot">
          <button type="button" aria-expanded={open === c.id} aria-controls={`wp-posts-${c.id}`} onClick={() => setOpen(open === c.id ? null : c.id)}>
            {open === c.id ? 'Zwiń wpisy' : `Zobacz wpisy (${c.posts_count})`}</button>
          {open === c.id && <ul id={`wp-posts-${c.id}`} className="sc-wp__posts">{c.posts.map(p => <li key={p.url}>
            <a href={p.url} target="_blank" rel="noopener noreferrer">@{p.handle}<time dateTime={p.published_at}>{when(p.published_at)}</time><span aria-hidden="true">↗</span></a></li>)}</ul>}
        </footer>
      </li>;
    })}</ol>}
    <aside className="sc-wp__method" aria-label="Jak liczymy">
      <h2>Jak liczymy</h2>
      <ul>
        <li>Porównujemy kolejne pięciowyrazowe fragmenty wpisów (bez linków, oznaczeń @ i&nbsp;interpunkcji). Łączymy wpisy, które mają co najmniej 80% wspólnych fragmentów.</li>
        <li>Pokazujemy grupę, gdy w&nbsp;ciągu 6 godzin napisały ją co najmniej 3 różne konta. Podania dalej i&nbsp;bardzo krótkie wpisy pomijamy.</li>
        <li>Te same progi dla każdego obozu i&nbsp;każdej partii. Partię przypisujemy tylko z&nbsp;potwierdzonego profilu konta.</li>
        <li>Usunięte wpisy znikają z&nbsp;listy razem z&nbsp;treścią.</li>
      </ul>
    </aside>
  </section>;
}
