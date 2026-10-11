"use client";
import { Sprostowanie } from './Sprostowanie';
import { useEffect, useMemo, useState } from 'react';
import { Loading } from '@spin-clinic/ui/kit';
import { Bar, Follow, Foot, Icon, LayerCaption, day, nb, plural, short, spinColor, text, useNarrativeLayer, useStandalone, type Access } from './ui';
import { ProfileOpenData, SejmVideos, type OpenData, type SejmVideo } from './OpenData';
import { WMediach } from './WMediach';
import { Przybornik, personTools } from './Przybornik';
import { sumLine } from './DrzewoPieniedzy';

/**
 * Profil osoby bez tematu (sprint 1, właściciel 6.10: „najlepsze narzędzie OSINT”): wszystko o jednej osobie publicznej
 * w jednym miejscu. Liczby, wykres aktywności, oś czasu (wpisy z diagnozami, dokumenty Sejmu, głosowania, artykuły),
 * funkcje i KRS z boku, na dole „Wspólne mianowniki”. Diagnozy i spin ze spin.clinic tylko w warstwie „Wpływ na narrację” (domyślnie wyłączonej). Ten sam język co strona tematu (px-*): jeden akcent, równe boksy.
 */
type Ev = { kind: string; label: string; url: string };
type Person = { id: number | null; slug: string | null; name: string; role: string };
type ProfileMaterial = { id: number; title: string; url: string; source: string; published_date: string | null; material_type?: string; kind_label?: string; snippet?: string; text_changed?: { type: string; detected_at: string } | null };
type Profile = {
  id: number; slug: string; name: string; role_title: string; organisation: string; status: string;
  party?: string | { code: string; short: string; name: string } | null; access?: Access;
  committees?: { code: string; name: string; role: string; since: string | null; url: string }[];
  official_profile_url?: string; evidence_url?: string; krs_note: string; generated_at: string;
  x_accounts: { handle: string; url: string; evidence_url: string }[];
  posts: { count: number; diagnoses: number; avg_spin: number | null; results: { id: number; url: string; text: string; date: string; handle: string;
    diagnosis: { id: number; intensity: number; headline: string; url: string } | null }[] };
  documents: { available: boolean; count: number; by_kind: Record<string, number>; results: { id: number; kind: string; label: string; title: string; date: string | null; url: string; replies: number | null }[] };
  votes: { available: boolean; count: number; summary: Record<string, number>; reason: string; results: { date: string | null; title: string; motion: string; vote: string; club: string; url: string }[];
    deviation?: { term: number; club: string; share: number; club_median: number | null; flagged: boolean; counted: number; rebellions_total: number; latest: { url: string; title: string; date: string | null } | null } | null };
  organisations: { id: number; name: string; krs_number: string; official_register_url: string; extra_register_url?: string; since_note?: string; public_role: string; organ: string; relation_status: string; since?: string | null; until?: string | null }[];
  employment_timeline: { position: string; organisation: string; status: string; since?: string | null; until?: string | null; source?: { url: string } }[];
  materials: { count: number; results: ProfileMaterial[] };
  mentions?: { results: ProfileMaterial[] };
  activity: { month: string; posts: number; documents: number; votes: number; media: number }[];
  topics: { topic: string; at: string }[];
  sejm_video?: SejmVideo[];
  open_data?: OpenData;
  // Drzewo przepływu pieniędzy (właściciel 6.10): podmioty osoby z KRS z sumami gałęzi; null = funkcja zamknięta
  money_trail?: null | { note: string; results: { id: number; name: string; krs_number: string; role: string; status: string; url: string; identifiers_missing: boolean;
    contracts: { count: number; sums: { currency: string; total: number }[] }; grants: { count: number; sums: { currency: string; total: number }[] }; people: number; unlinked: number }[] };
  denominators: null | { note: string; people: (Person & { score: number; shared: Record<string, number>; evidence: Ev[] })[];
    krs: (Person & { count: number; evidence: Ev[] })[];
    votes: { available: boolean; window: number; club?: string; aligned: (Person & { club: string; pct: number; shared: number; agreed: number; evidence: Ev[] })[];
      cross_club: (Person & { club: string; pct: number; shared: number; agreed: number; evidence: Ev[] })[] } };
};
type Item = { id: string; kind: 'statement' | 'record' | 'vote' | 'media'; date: string; source: string; text: string; url: string; spin?: { intensity: number; headline: string; url: string }; vote?: string };

const VOTE_ORDER = ['za', 'przeciw', 'wstrzymał się', 'nieobecny'];
const SERIES = [['posts', 'wpisy na X'], ['documents', 'dokumenty Sejmu'], ['votes', 'głosowania'], ['media', 'artykuły']] as const;
const MONTHS = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];
const month = (m: string) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(2, 4)}`;

export function PersonProfile({ ident }: { ident: string }) {
  useStandalone();
  const [data, setData] = useState<Profile | null>(null);
  const [state, setState] = useState<'loading' | 'idle' | 'missing' | 'off' | 'error'>('loading');
  useEffect(() => {
    fetch(`/api/przeszlosc/osoba/${encodeURIComponent(ident)}/`).then(async r => {
      if (r.status === 404) { const body = await r.json().catch(() => ({})); setState(String(body.detail ?? '').includes('wyłączona') ? 'off' : 'missing'); return; }
      if (!r.ok) throw new Error();
      const d: Profile = await r.json(); setData(d); setState('idle');
      if (d.slug && d.slug !== ident) window.history.replaceState(null, '', `/przeszlosc/osoba/${d.slug}${window.location.search}`);
      document.title = `${d.name} - przeszłość.today`;
    }).catch(() => setState('error'));
  }, [ident]);
  return <main className="px px-pp">
    <Bar />
    {state === 'loading' && <div className="px-wait"><Loading label="Ładowanie profilu" /></div>}
    {state === 'missing' && <p className="px-msg">{nb('Nie ma takiej osoby w rejestrze osób publicznych.')} <a href="/przeszlosc?tryb=osoba">Szukaj osoby</a></p>}
    {state === 'off' && <p className="px-msg">Podgląd jest jeszcze wyłączony na serwerze.</p>}
    {state === 'error' && <p className="px-msg" role="alert">Nie udało się pobrać profilu. Spróbuj ponownie.</p>}
    {data && <ProfileView data={data} />}
    <Foot />
  </main>;
}

function ProfileView({ data }: { data: Profile }) {
  const [narr] = useNarrativeLayer();
  const [kindState, setKind] = useState('all');
  const kind = !narr && kindState === 'diag' ? 'all' : kindState;
  const [more, setMore] = useState(false);
  const items = useMemo<Item[]>(() => [
    ...data.posts.results.map(p => ({ id: `p${p.id}`, kind: 'statement' as const, date: p.date, source: `@${p.handle}`, text: p.text, url: p.url,
      spin: narr && p.diagnosis ? { intensity: p.diagnosis.intensity, headline: p.diagnosis.headline, url: p.diagnosis.url } : undefined })),
    ...data.documents.results.filter(d => d.date).map(d => ({ id: `d${d.id}`, kind: 'record' as const, date: d.date!, source: d.label + (d.replies ? ` · odpowiedzi: ${d.replies}` : ''), text: d.title, url: d.url })),
    ...data.votes.results.filter(v => v.date).map((v, i) => ({ id: `v${i}`, kind: 'vote' as const, date: v.date!, source: 'Głosowanie w Sejmie', text: v.title, url: v.url, vote: v.vote })),
    ...data.materials.results.filter(m => m.published_date).map(m => ({ id: `m${m.id}`, kind: 'media' as const, date: m.published_date!.slice(0, 10), source: m.source, text: m.title, url: m.url })),
  ].sort((a, b) => b.date.localeCompare(a.date)), [data, narr]);
  const shown = items.filter(i => kind === 'all' || (kind === 'diag' ? Boolean(i.spin) : i.kind === kind));
  const visible = more ? shown : shown.slice(0, 12);
  const sub = [data.role_title, data.party, data.organisation].map(text).filter(Boolean).join(' · ');
  const locked = new Set(data.access?.locked ?? []);
  const committees = data.committees ?? [];
  const inSejm = [committees.length ? `${committees.length} ${plural(committees.length, 'komisja', 'komisje', 'komisji')}` : '',
    ...Object.entries(data.documents.by_kind).sort((a, b) => b[1] - a[1]).slice(0, committees.length ? 2 : 3).map(([k, n]) => `${k}: ${n}`)].filter(Boolean);
  const stamp = data.generated_at.slice(0, 10);
  let lastDay = '';
  return <>
    <header className="px-tv__head px-pp__head">
      <div>
        <p className="px-kicker">Osoba publiczna<LayerCaption /></p>
        <h1>{data.name}</h1>
        {sub && <p className="px-pp__sub">{sub}</p>}
        <p className="px-pp__links">
          <a href={`/przeszlosc/przeplyw/${encodeURIComponent(`osoba:${data.slug || data.id}`)}`}>Drzewo przepływu →</a>
          {data.official_profile_url && <a href={data.official_profile_url} target="_blank" rel="noopener noreferrer">Oficjalny profil ↗</a>}
          {data.evidence_url && <a href={data.evidence_url} target="_blank" rel="noopener noreferrer">Źródło funkcji ↗</a>}
          {data.x_accounts.map(a => <a key={a.handle} href={a.url} target="_blank" rel="noopener noreferrer">@{a.handle} na X ↗</a>)}
        </p>
      </div>
      <div className="px-tv__tools">
        <Sprostowanie recordId={`osoba:${data.slug || data.id}`} label={data.name} />
        {!locked.has('alerts') && <Follow kind="person" target={data.slug} label={data.name} />}
        {!locked.has('export') && <><a className="px-tool" href={`/api/przeszlosc/osoba/${data.id}/?eksport=csv`} download><Icon name="down" />CSV</a>
        <a className="px-tool" href={`/api/przeszlosc/osoba/${data.id}/?eksport=json`} download><Icon name="down" />JSON</a></>}
      </div>
    </header>

    <section className="px-proof px-pp__proof" aria-label="Liczby" data-n={narr ? 6 : 5}>
      {([[data.posts.count, 'wpisów na X', 'wpis na X', 'wpisy na X'], [data.posts.diagnoses, 'diagnoz Dr. Spina', 'diagnoza Dr. Spina', 'diagnozy Dr. Spina'],
        [data.documents.count, 'dokumentów Sejmu', 'dokument Sejmu', 'dokumenty Sejmu'], [data.votes.count, 'głosowań imiennych', 'głosowanie imienne', 'głosowania imienne'],
        [data.organisations.length, 'funkcji w KRS', 'funkcja w KRS', 'funkcje w KRS'], [data.materials.count, 'artykułów', 'artykuł', 'artykuły']] as const)
        .filter(([, many]) => narr || many !== 'diagnoz Dr. Spina').map(([n, many, one, few]) => <div key={many}><b>{n.toLocaleString('pl-PL')}</b><span>{nb(plural(n, one, few, many))}</span></div>)}
    </section>

    <div className="px-pp__sum">
      <Activity rows={data.activity} />
      <section className="px-card px-brief" aria-labelledby="pp-brief-h">
        <h3 id="pp-brief-h" className="px-h3">W skrócie</h3>
        <dl>
          {narr && <div><dt>Średni spin</dt><dd>{data.posts.avg_spin !== null ? <><i className="px-spin-dot" style={{ ['--spin' as string]: spinColor(data.posts.avg_spin) }} />{data.posts.avg_spin}/100 <small>· {data.posts.diagnoses} {plural(data.posts.diagnoses, 'diagnoza', 'diagnozy', 'diagnoz')}</small></> : <small>brak diagnoz</small>}</dd></div>}
          <div><dt>Głosowania</dt><dd>{data.votes.count ? <VoteBar summary={data.votes.summary} /> : <small>{data.votes.available ? 'brak w bazie' : 'nie jest posłem w naszych danych'}</small>}</dd></div>
          {data.votes.deviation && <div><dt>Odstępstwa od klubu</dt><dd>{pctPl(data.votes.deviation.share)} <small>· mediana {data.votes.deviation.club} {data.votes.deviation.club_median === null ? '-' : pctPl(data.votes.deviation.club_median)}
            {data.votes.deviation.latest ? <> · <a href={data.votes.deviation.latest.url} target="_blank" rel="noopener noreferrer">{data.votes.deviation.rebellions_total} wbrew klubowi ↗</a></> : ''}</small></dd></div>}
          <div><dt>W Sejmie</dt><dd>{inSejm.length ? inSejm.join(' · ') : <small>brak dokumentów w bazie</small>}</dd></div>
          <div><dt>Ostatnio</dt><dd>{items[0] ? <>{day(items[0].date)} <small>· {items[0].source}</small></> : <small>brak aktywności w bazie</small>}</dd></div>
        </dl>
        <p className="px-card__foot">Policzone z&nbsp;danych poniżej, bez AI. Stan na {day(stamp)}.</p>
      </section>
    </div>

    <div className="px-grid">
      <div className="px-main">
        <section className="px-time" aria-labelledby="pp-os-h">
          <div className="px-time__head"><h2 id="pp-os-h" className="px-h3">Oś czasu</h2><span>{shown.length} {plural(shown.length, 'pozycja', 'pozycje', 'pozycji')}</span></div>
          <div className="px-filters"><div className="px-seg" role="group" aria-label="Rodzaj">
            {([['all', 'Wszystko'], ['statement', 'Wpisy'], ['diag', 'Z diagnozą'], ['record', 'Sejm'], ['vote', 'Głosowania'], ['media', 'Media']] as const).filter(([k]) => narr || k !== 'diag').map(([k, l]) =>
              <button key={k} type="button" aria-pressed={kind === k} onClick={() => { setKind(k); setMore(false); }}>{l}</button>)}
          </div></div>
          {!shown.length && <p className="px-note">{nb('Nic w tym filtrze. Zmień rodzaj.')}</p>}
          <ol className="px-events">{visible.map(n => {
            const head = n.date !== lastDay ? <li className="px-day" key={`d${n.date}`}>{day(n.date)}</li> : null;
            lastDay = n.date;
            return [head, <li key={n.id} className="px-ev" data-kind={n.kind}>
              <div className="px-ev__meta"><span className="px-ev__ic"><Icon name={n.kind} /></span><b>{n.source}</b><time dateTime={n.date}>{short(n.date)}</time></div>
              <p className="px-ev__text">{n.text}</p>
              <div className="px-ev__act">
                {n.spin ? <a className="px-link" href={n.spin.url} target="_blank" rel="noopener noreferrer"><i className="px-spin-dot" style={{ ['--spin' as string]: spinColor(n.spin.intensity) }} />Diagnoza Dr. Spina · spin {n.spin.intensity}/100 ↗</a>
                  : n.vote ? <span className="px-pp__vote" data-v={n.vote}><i />głos: {n.vote}</span> : null}
                <span className="px-ev__quiet">
                  {n.url && <a className="px-quiet" href={n.url} target="_blank" rel="noopener noreferrer">źródło ↗</a>}
                  {n.url && n.kind !== 'vote' && <a className="px-quiet" href={`https://web.archive.org/web/*/${n.url}`} target="_blank" rel="noopener noreferrer">archiwum</a>}
                </span>
              </div>
            </li>];
          })}</ol>
          {shown.length > 12 && <button type="button" className="px-more" onClick={() => setMore(!more)}>{more ? 'Pokaż mniej' : `Pokaż wszystko (${shown.length})`}</button>}
        </section>
        {/* „W mediach” (właściciel 6.10): potwierdzone artykuły o osobie; tylko tytuł, data, redakcja i odnośnik */}
        <WMediach id="pp-wm-h" items={data.materials.results.filter(m => m.url).map(m => ({ id: `wm${m.id}`, outlet: m.source || 'Media', date: m.published_date ? m.published_date.slice(0, 10) : null, title: m.title, url: m.url, material_type: m.material_type, kind_label: m.kind_label, snippet: m.snippet, changed: m.text_changed ? m.text_changed.detected_at.slice(0, 10) : null }))} />
        <WMediach id="pp-mentions-h" heading="Wzmianki" automatic items={(data.mentions?.results ?? []).filter(m => m.url).map(m => ({ id: `mention${m.id}`, outlet: m.source || 'Media', date: m.published_date ? m.published_date.slice(0, 10) : null, title: m.title, url: m.url, material_type: m.material_type, kind_label: m.kind_label, snippet: m.snippet, changed: m.text_changed ? m.text_changed.detected_at.slice(0, 10) : null }))} />
      </div>
      <aside className="px-side">
        <section className="px-card" aria-labelledby="pp-roles-h">
          <h3 id="pp-roles-h" className="px-h3">Funkcje publiczne</h3>
          <ul className="px-panel__rows">{data.employment_timeline.slice(0, 8).map((r, i) => <li key={i}><span>{r.source?.url ? <a href={r.source.url} target="_blank" rel="noopener noreferrer">{r.position}</a> : r.position}</span>
            <small>{[r.organisation, r.since ? `od ${day(r.since)}` : '', r.until ? `do ${day(r.until)}` : '', r.status === 'current' ? 'obecnie' : 'wcześniej'].filter(Boolean).join(' · ')}</small></li>)}</ul>
        </section>
        {committees.length > 0 && <section className="px-card" aria-labelledby="pp-com-h">
          <h3 id="pp-com-h" className="px-h3">Komisje sejmowe <small>{committees.length}</small></h3>
          <ul className="px-panel__rows">{committees.map(c => <li key={c.code}>
            <a href={c.url} target="_blank" rel="noopener noreferrer">{c.name}</a>
            <small>{[c.role, c.since ? `od ${day(c.since)}` : ''].filter(Boolean).join(' · ')}</small></li>)}</ul>
          <p className="px-note">{nb('Skład komisji z oficjalnego API Sejmu, po identyfikatorze posła.')}</p>
        </section>}
        <section className="px-card" aria-labelledby="pp-krs-h">
          <h3 id="pp-krs-h" className="px-h3">Funkcje w KRS</h3>
          {locked.has('krs') ? <p className="px-note">{nb('Funkcje w KRS są w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>
          : data.organisations.length ? <ul className="px-panel__rows">{data.organisations.map(o => <li key={`${o.id}-${o.public_role}-${o.relation_status}`}>
            <a href={o.official_register_url} target="_blank" rel="noopener noreferrer">{o.name}</a>
            <small>{[o.organ || o.public_role, `KRS ${o.krs_number}`, o.since ? `wpis w KRS od ${day(o.since)}` : '', o.relation_status === 'former' ? 'historyczna' : 'obecna'].filter(Boolean).join(' · ')}{o.extra_register_url ? <> · <a href={o.extra_register_url} target="_blank" rel="noopener noreferrer">rejestr.io</a></> : null}</small></li>)}</ul>
            : <p className="px-note">{nb(`Brak w naszych danych: potwierdzonych funkcji w KRS (zakres: osoby publiczne z naszej bazy, stan na ${day(stamp)}).`)}</p>}
          <p className="px-note">{nb(data.organisations.find(o => o.since_note)?.since_note ?? 'Data wpisu w KRS nie zawsze jest datą faktycznego objęcia funkcji.')}</p>
          <p className="px-note">{nb(data.krs_note)}</p>
        </section>
        <section className="px-card" aria-labelledby="pp-money-h">
          <h3 id="pp-money-h" className="px-h3">Pieniądze powiązanych spółek</h3>
          {locked.has('money_trail') || data.money_trail === null ? <p className="px-note">{nb('Drzewo przepływu pieniędzy jest w pilotażu przeszłość.today.')} <a href="/przeszlosc/pilot">Pilotaż</a></p>
          : data.money_trail?.results.length ? <ul className="px-panel__rows">{data.money_trail.results.map(o => <li key={o.id}>
            <a href={o.url}>{o.name}</a>
            <small>{[`zamówienia: ${o.contracts.count}${o.contracts.sums.length ? ` (${sumLine(o.contracts.sums)})` : ''}`, `dotacje UE: ${o.grants.count}${o.grants.sums.length ? ` (${sumLine(o.grants.sums)})` : ''}`,
              `osoby: ${o.people}`, o.identifiers_missing ? 'bez NIP w bazie' : ''].filter(Boolean).join(' · ')}</small></li>)}</ul>
            : <p className="px-note">{nb('Brak podmiotów z KRS, dla których moglibyśmy zbudować drzewo.')}</p>}
          <p className="px-note">{nb('Każdy podmiot otwiera drzewo: zamówienia (TED, BZP), dotacje UE (FTS) i osoby, łączone tylko po NIP, KRS i REGON.')}</p>
        </section>
        {data.topics.length > 0 && <section className="px-card" aria-labelledby="pp-topics-h">
          <h3 id="pp-topics-h" className="px-h3">W tematach dnia</h3>
          <div className="px-chips">{data.topics.map(t => <a key={t.topic} className="px-pp__chip" href={`/przeszlosc?q=${encodeURIComponent(t.topic)}&osoba=figure:${data.id}`}>{t.topic}</a>)}</div>
        </section>}
        {narr && <SejmVideos items={data.sejm_video ?? []} />}
        <ProfileOpenData data={data.open_data} />
        <Przybornik id="pp-tools-h" tools={personTools({ name: data.name })} />
      </aside>
    </div>

    {data.denominators && <Denominators data={data} />}
  </>;
}

const pctPl = (v: number) => `${v.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}%`;

function VoteBar({ summary }: { summary: Record<string, number> }) {
  const total = Object.values(summary).reduce((a, b) => a + b, 0) || 1;
  return <span className="px-pp__votebar">
    <i aria-hidden="true">{VOTE_ORDER.map(k => summary[k] ? <b key={k} data-v={k} style={{ flexGrow: summary[k] }} /> : null)}</i>
    <small>{VOTE_ORDER.filter(k => summary[k]).map(k => `${Math.round((100 * summary[k]) / total)}% ${k}`).join(', ')}</small>
  </span>;
}

/* Aktywność w 12 miesiącach: słupki skumulowane, wpisy akcentem, reszta odcieniami tekstu (jedno wyróżnienie). */
function Activity({ rows }: { rows: Profile['activity'] }) {
  const max = Math.max(1, ...rows.map(r => r.posts + r.documents + r.votes + r.media));
  const total = rows.reduce((a, r) => a + r.posts + r.documents + r.votes + r.media, 0);
  const w = 100 / rows.length;
  return <section className="px-card px-chart px-pp__chart" aria-labelledby="pp-chart-h">
    <h3 id="pp-chart-h" className="px-h3">Aktywność <small>12 miesięcy</small></h3>
    <div className="px-pp__plot">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`Aktywność od ${month(rows[0].month)} do ${month(rows[rows.length - 1].month)}: ${total} pozycji`}>
        <line x1="0" x2="100" y1="99.5" y2="99.5" vectorEffect="non-scaling-stroke" />
        {rows.map((r, i) => { let y = 100; return <g key={r.month}><title>{`${month(r.month)}: ${SERIES.map(([k, l]) => `${l} ${r[k]}`).join(', ')}`}</title>
          {SERIES.map(([k]) => { const h = (94 * r[k]) / max; y -= h; return h > 0 ? <rect key={k} data-s={k} x={i * w + w * .16} y={y} width={w * .68} height={h} /> : null; })}</g>; })}
      </svg>
      {!total && <p className="px-note px-pp__empty">{nb('Brak aktywności w bazie w ostatnich 12 miesiącach.')}</p>}
    </div>
    <div className="px-card__foot px-pp__axis"><span>{month(rows[0].month)}</span>
      <ul className="px-pp__legend">{SERIES.map(([k, l]) => <li key={k}><i data-s={k} />{l}</li>)}</ul><span>{month(rows[rows.length - 1].month)}</span></div>
  </section>;
}

/* Wspólne mianowniki v1: trzy równe boksy, po 10 pozycji; każda pozycja z dowodami (linki do źródeł). */
function Denominators({ data }: { data: Profile }) {
  const d = data.denominators!;
  const [cross, setCross] = useState(false);
  const votes = cross ? d.votes.cross_club : d.votes.aligned;
  return <section className="px-sec px-dn" aria-labelledby="dn-h">
    <div className="px-dn__head"><h2 id="dn-h" className="px-h2">Wspólne mianowniki</h2><p className="px-note">{nb(d.note)}</p></div>
    <div className="px-dn__grid">
      <DnCard title="Występują razem" icon="people" empty="Brak wspólnych dokumentów, tematów i przekazów w bazie."
        foot="Wspólne interpelacje i dokumenty Sejmu, tematy dnia i przekazy dnia."
        rows={d.people.map(p => ({ person: p, value: `${p.score}`, valueLabel: 'punkty zbieżności', meta: Object.entries(p.shared).map(([k, n]) => `${k}: ${n}`).join(', '), evidence: p.evidence }))} />
      <DnCard title="Te same podmioty w KRS" icon="organisation" empty="Brak innych osób z funkcjami w tych samych podmiotach."
        foot={data.krs_note}
        rows={d.krs.map(p => ({ person: p, value: `${p.count}`, valueLabel: 'wspólne podmioty', meta: p.role, evidence: p.evidence }))} />
      <DnCard title="Zgodne głosy" icon="vote" empty={d.votes.available ? 'Za mało wspólnych głosowań.' : 'Dotyczy posłów z oficjalnym identyfikatorem Sejmu.'}
        foot={d.votes.available ? `Zgodność za/przeciw/wstrzymał się w ${d.votes.window} ostatnich głosowaniach tej osoby.` : 'Tylko głosowania imienne z oficjalnych danych Sejmu.'}
        tools={d.votes.available ? <div className="px-seg px-dn__seg" role="group" aria-label="Zakres">
          <button type="button" aria-pressed={!cross} onClick={() => setCross(false)}>Ogółem</button>
          <button type="button" aria-pressed={cross} onClick={() => setCross(true)}>Inne kluby</button></div> : null}
        rows={votes.map(p => ({ person: p, value: `${p.pct}%`, valueLabel: `zgodność w ${p.shared} głosowaniach`, meta: [p.club, `${p.agreed}/${p.shared}`].filter(Boolean).join(' · '), evidence: p.evidence }))} />
    </div>
  </section>;
}

type Row = { person: Person; value: string; valueLabel: string; meta: string; evidence: Ev[] };
function DnCard({ title, icon, rows, empty, foot, tools }: { title: string; icon: string; rows: Row[]; empty: string; foot: string; tools?: React.ReactNode }) {
  const [open, setOpen] = useState<number | null>(null);
  return <section className="px-card px-dn__card" aria-label={title}>
    <header className="px-dn__top"><h3 className="px-h3"><Icon name={icon} />{title}</h3>{tools}</header>
    {rows.length ? <ol className="px-dn__list">{rows.slice(0, 10).map((r, i) => <li key={`${r.person.id ?? r.person.name}-${i}`} data-open={open === i || undefined}>
      <div className="px-dn__row">
        <span className="px-dn__n">{i + 1}</span>
        <span className="px-dn__who">{r.person.id ? <a href={r.person.slug ? `/przeszlosc/osoba/${r.person.slug}` : `/przeszlosc/osoba/${r.person.id}`}>{r.person.name}</a> : <b>{r.person.name}</b>}
          <small>{r.meta}</small></span>
        <em title={r.valueLabel}>{r.value}</em>
        <button type="button" className="px-dn__more" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)} disabled={!r.evidence.length}
          aria-label={`Dowody (${r.evidence.length}): ${r.person.name}`} title="Pokaż dowody"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
            strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg></button>
      </div>
      {open === i && <ul className="px-dn__ev">{r.evidence.map((e, j) => <li key={j}><span>{e.kind}</span>
        <a href={e.url} target={e.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{e.label}</a></li>)}</ul>}
    </li>)}</ol> : <p className="px-note px-dn__empty">{nb(empty)}</p>}
    <p className="px-card__foot">{nb(foot)}</p>
  </section>;
}
