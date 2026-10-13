"use client";
import { useEffect, useState } from 'react';
import './odstepstwa.css';

/**
 * Odstępstwa od klubu (plan Architekta 6.10): kto głosuje inaczej niż większość swojego klubu.
 * Liczone co noc z oficjalnych głosowań Sejmu (news/voting_anomalies.py), te same progi dla każdego klubu.
 * Słownictwo neutralne: odstępstwo to informacja, nie zarzut.
 */
type Event = { id: string; date: string | null; title: string; url: string; mp_id: number; name: string; club: string; vote: string; club_vote: string; unity: number };
type Member = { mp_id: number; name: string; club: string; counted: number; deviations: number; share: number; club_median: number | null; excess: number | null; flagged: boolean; rebellions_total: number; latest: Event | null };
type Club = { club: string; mps: number; members: number; median: number | null; flagged: Member[]; rebellions_total: number; rebellions: Event[] };
type Data = { term: number | null; period: string; computed_at: string | null; votings: number; range: { from: string | null; to: string | null }; method: string; clubs: Club[] };

const LIST = 6;
const pct = (v: number | null) => v === null ? '-' : `${v.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}%`;
const day = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
const short = (d?: string | null) => d ? new Date(d).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }) : '';
const nice = (name: string) => name.split(/(\s+|-)/).map(w => w.length > 3 && w === w.toUpperCase() && w !== w.toLowerCase() ? w[0] + w.slice(1).toLowerCase() : w).join('');

export function Odstepstwa({ standalone = false, compact = false }: { standalone?: boolean; compact?: boolean }) {
  const [period, setPeriod] = useState<'90d' | 'kadencja'>('90d');
  const [data, setData] = useState<Data | null>(null);
  const [club, setClub] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch(`/api/przeszlosc/odstepstwa/?okres=${period}`).then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Data) => { if (!live) return; setData(d); setFailed(false); setClub(c => d.clubs.some(x => x.club === c) ? c : d.clubs[0]?.club ?? null); })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [period]);
  // na stronie głównej sekcja znika bez danych; na osobnej stronie zawsze komunikat (stała strefa, nic nie skacze)
  if (failed && !data) return standalone ? <p className="px-msg" role="alert">Nie udało się pobrać odstępstw. Spróbuj ponownie za chwilę.</p> : null;
  if (data && !data.clubs.length) return standalone ? <p className="px-msg">Brak danych o odstępstwach w tym okresie.</p> : null;
  const current = data?.clubs.find(c => c.club === club) ?? data?.clubs[0];
  // strona główna (recenzja Fable 13.10: sekcja miała 781 / 1953 px): jedna zwarta karta z liczbami i odnośnikiem do pełnego zestawienia
  if (compact && !data) return null;
  if (compact && data) {
    const total = data.clubs.reduce((a, c) => a + c.rebellions_total, 0);
    return <section className="px-sec px-dev px-dev--compact" id="odstepstwa" aria-labelledby="dev-h">
      <h2 id="dev-h" className="px-h2">Odstępstwa od klubu</h2>
      <p className="px-dev__method">Odstępstwo to głos inny niż większość własnego klubu w&nbsp;tym głosowaniu. Te same progi dla każdego klubu; odstępstwo nie jest zarzutem.</p>
      <div className="pt-devsum">
        <dl>
          <div><dt>Głosowania Sejmu w zestawieniu</dt><dd>{data.votings.toLocaleString('pl-PL')}</dd></div>
          <div><dt>Kluby i koła</dt><dd>{data.clubs.length}</dd></div>
          <div><dt>Głosy inne niż większość klubu przy zgodności klubu ≥ 80%</dt><dd>{total.toLocaleString('pl-PL')}</dd></div>
        </dl>
        <p className="px-note px-dev__range">{data.range.from ? `${day(data.range.from)} - ${day(data.range.to)}` : ''}{data.term ? ` · kadencja ${data.term}` : ''}{data.computed_at ? ` · liczone ${day(data.computed_at)}` : ''}</p>
        <p className="pt-devsum__more"><a className="px-link" href="/przeszlosc/odstepstwa">Zestawienie według klubów&nbsp;→</a></p>
      </div>
    </section>;
  }
  return <section className="px-sec px-dev" id="odstepstwa" aria-labelledby="dev-h">
    <div className="px-dev__head">
      {standalone ? <div className="pt-head__l"><p className="px-kicker">Głosowania Sejmu</p><h1 id="dev-h">Odstępstwa od klubu</h1></div>
        : <h2 id="dev-h" className="px-h2">Odstępstwa od klubu</h2>}
      <div className="px-seg" role="group" aria-label="Okres">
        {([['90d', '90 dni'], ['kadencja', 'Cała kadencja']] as const).map(([k, l]) =>
          <button key={k} type="button" aria-pressed={period === k} onClick={() => setPeriod(k)}>{l}</button>)}
      </div>
    </div>
    <p className="px-dev__method">Odstępstwo to głos inny niż większość własnego klubu w&nbsp;tym głosowaniu. Te same progi dla każdego klubu; odstępstwo nie jest zarzutem.</p>
    {data && <p className="px-note px-dev__range">{data.range.from ? `${day(data.range.from)} - ${day(data.range.to)}` : ''} · {data.votings.toLocaleString('pl-PL')} głosowań Sejmu
      {data.term ? ` · kadencja ${data.term}` : ''}</p>}
    {data && <div className="px-dev__tabs" role="tablist" aria-label="Klub">
      {data.clubs.map(c => <button key={c.club} type="button" role="tab" id={`dev-tab-${c.club}`} aria-selected={c.club === current?.club}
        aria-controls="dev-panel" onClick={() => setClub(c.club)}>{c.club}<small>{c.members}</small></button>)}
    </div>}
    {current && <div className="px-dev__grid" id="dev-panel" role="tabpanel" aria-labelledby={`dev-tab-${current.club}`}>
      <section className="px-card px-dev__card" aria-labelledby="dev-mps-h">
        <h3 id="dev-mps-h" className="px-h3">Wyższy udział głosów innych niż większość klubu <small>{current.flagged.length}</small></h3>
        {current.flagged.length ? <ol className="px-dev__list">{current.flagged.slice(0, LIST).map(m => <li key={m.mp_id}>
          {m.latest ? <a href={m.latest.url} target="_blank" rel="noopener noreferrer" title={`Ostatni głos inny niż większość klubu: ${m.latest.title}`}>
            <b>{nice(m.name)}</b><span className="px-dev__val">{pct(m.share)}</span>
            <small>{m.deviations} z&nbsp;{m.counted} głosów · ostatnio {short(m.latest.date)}: {m.latest.vote}, klub {m.latest.club_vote} ↗</small></a>
            : <div><b>{nice(m.name)}</b><span className="px-dev__val">{pct(m.share)}</span><small>{m.deviations} z&nbsp;{m.counted} głosów</small></div>}
        </li>)}</ol> : <p className="px-dev__empty">Brak posłów, u&nbsp;których udział głosów innych niż większość klubu jest wyższy od mediany o&nbsp;więcej niż 5&nbsp;pkt proc.</p>}
        <p className="px-card__foot">Mediana klubu: {pct(current.median)} · porównano {current.mps} {current.mps === 1 ? 'posła' : 'posłów'} z&nbsp;co najmniej 20 głosami</p>
      </section>
      <section className="px-card px-dev__card" aria-labelledby="dev-reb-h">
        <h3 id="dev-reb-h" className="px-h3">Głosy inne niż większość klubu <small>{current.rebellions_total}</small></h3>
        {current.rebellions.length ? <ol className="px-dev__list">{current.rebellions.slice(0, LIST).map(e => <li key={`${e.id}-${e.mp_id}`}>
          <a href={e.url} target="_blank" rel="noopener noreferrer"><b>{nice(e.name)}</b><span className="px-dev__val">{short(e.date)}</span>
            <small>{e.vote}, klub {e.club_vote} ({e.unity}%) · {e.title} ↗</small></a>
        </li>)}</ol> : <p className="px-dev__empty">Brak głosów innych niż większość klubu przy zgodności klubu w&nbsp;tym okresie.</p>}
        <p className="px-card__foot">Gdy co najmniej 80% klubu głosowało tak samo</p>
      </section>
    </div>}
  </section>;
}
