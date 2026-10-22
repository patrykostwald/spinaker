"use client";
import { useMemo, type ReactNode } from 'react';
import './najwazniejsze.css';
import { buildLanding, LANDING_TITLE, nb, SHOWN_ORGS, ymd, type LandingInput, type OrgRow, type SourceRef, type Tile } from './najwazniejsze-dane';

/**
 * Landing profilu osoby "Najważniejsze" (właściciel 13.10: "wchodząc na daną osobę musimy mieć landing, gdzie są wszystkie
 * najważniejsze elementy"). Schemat kafla: etykieta (góra), jedna duża liczba albo stan, 1-3 linie wyjaśnienia (środek 1fr),
 * źródło z datą i odnośnik "Zobacz wszystko →" (dół, dociągnięty). Kafel 1 (fundacje i spółki z KRS) jest jedynym wyróżnieniem
 * (2 kolumny x 2 wiersze, tło surface-2). Dane tylko z profilu API; brak = "brak w naszych danych" z zakresem i datą.
 * Logika w najwazniejsze-dane.ts (funkcje czyste, test 121).
 */
type Filter = 'record' | 'vote';

function Sources({ list, stamp }: { list: SourceRef[]; stamp: string }) {
  return <p className="pt-tile__source" data-pt-source>
    {list.length > 0 && <>Źródło: {list.map((s, i) => <span key={`${s.label}-${i}`}>{i > 0 ? ', ' : ''}{s.url
      ? <a href={s.url} target={s.url.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{s.label}<i aria-hidden="true"> ↗</i></a> : s.label}</span>)}{' · '}</>}
    <time data-pt-stamp>{stamp}</time>
  </p>;
}

function More({ t, onFilter }: { t: Tile; onFilter?: (k: Filter) => void }) {
  const f = t.link.filter;
  return <a className="pt-tile__more" href={t.link.href} onClick={f ? () => onFilter?.(f) : undefined}
    aria-label={`${t.link.label.replace(/\s*→$/, '')}: ${t.label}`}>{t.link.label}</a>;
}

function OrgItem({ r }: { r: OrgRow }) {
  return <li className="pt-org" data-status={r.status}>
    <div className="pt-org__name">{r.href ? <a href={r.href}>{r.name}</a> : r.name}</div>
    <p className="pt-org__role">{r.type}{r.role ? ` · ${r.role}` : ''}</p>
    <p className="pt-org__date"><span>{r.period}</span><b>{r.statusText}</b></p>
    <p className="pt-org__source">{r.krs ? (r.krsUrl ? <a href={r.krsUrl} target="_blank" rel="noopener noreferrer">KRS {r.krs}<i aria-hidden="true"> ↗</i></a> : <span>KRS {r.krs}</span>)
      : <span>KRS: brak w naszych danych</span>}</p>
  </li>;
}

function TileView({ t, i, onFilter }: { t: Tile; i: number; onFilter?: (k: Filter) => void }) {
  const wide = t.id === 'podmioty';
  const strip = t.id === 'media';
  const hid = `${t.anchor}-h`;
  const shown = t.orgs.slice(0, SHOWN_ORGS);
  return <article id={t.anchor} className={`pt-tile${wide ? ' pt-tile--wide' : ''}${strip ? ' pt-tile--strip' : ''}`} data-tile={t.id} data-state={t.state}
    style={{ ['--i' as string]: i }} aria-labelledby={hid}>
    <header className="pt-tile__top">
      <h3 id={hid} className="pt-tile__l">{t.label}</h3>
      <div className="pt-tile__vu">
        <div className="pt-tile__v" data-pt-value>{t.value}</div>
        {t.unit && <p className="pt-tile__u">{t.unit}</p>}
      </div>
    </header>
    <div className="pt-tile__b">
      {t.lines.map((l, k) => <p key={k} className="pt-tile__x">{l}</p>)}
      {wide && shown.length > 0 && <ol className="pt-orgs" aria-label="Podmioty z KRS">{shown.map(r => <OrgItem key={r.key} r={r} />)}</ol>}
      {wide && t.orgs.length > shown.length && <p className="pt-tile__x pt-tile__x--quiet">Pokazano {shown.length} z {t.orgs.length}. Reszta jest w sekcji „Funkcje w KRS”.</p>}
      {t.docs.length > 0 && <ul className="pt-docs" aria-label="Oświadczenia majątkowe">{t.docs.map(d => <li key={d.key}>
        {d.url ? <a href={d.url} target="_blank" rel="noopener noreferrer">{d.meta !== undefined ? d.title : d.year ? `Oświadczenie za rok ${d.year}` : d.title}<i aria-hidden="true"> ↗</i></a> : <span>{d.title}</span>}
        {d.meta ? <small className="pt-docs__m">{d.meta}</small> : null}{d.auto ? <small className="pt-docs__a">{d.auto}</small> : null}</li>)}</ul>}
      {t.extra && <p className="pt-tile__x pt-tile__x--quiet">{t.extra.text} <a href={t.extra.href}>Drzewo pieniędzy →</a></p>}
    </div>
    <footer className="pt-tile__f">
      <Sources list={t.source} stamp={t.stampText} />
      <More t={t} onFilter={onFilter} />
    </footer>
  </article>;
}

export function Najwazniejsze({ data, onFilter, extra }: { data: LandingInput; onFilter?: (k: Filter) => void; extra?: ReactNode }) {
  const landing = useMemo(() => buildLanding(data), [data]);
  const [org, ...rest] = landing.tiles;
  const media = rest[rest.length - 1];
  const stats = rest.slice(0, -1);
  return <section className="pt-nw" id="pp-najwazniejsze" aria-labelledby="pp-nw-h" data-lean={landing.lean || undefined}>
    <div className="pt-nw__head">
      <h2 id="pp-nw-h" className="pt-nw__h">{nb(LANDING_TITLE)}</h2>
      <p className="pt-nw__meta">stan na {ymd(landing.stamp)}</p>
    </div>
    <p className="pt-nw__rule" data-pt-rule>{nb(landing.disclaimer)} <a href="/przeszlosc/jak-to-dziala">Jak to działa</a></p>
    <div className="pt-nw__grid">
      <TileView t={org} i={0} onFilter={onFilter} />
      {stats.map((t, k) => <TileView key={t.id} t={t} i={k + 1} onFilter={onFilter} />)}
    </div>
    <TileView t={media} i={stats.length + 1} onFilter={onFilter} />
    {/* dodatkowy pasek landingu (np. "Wcześniej i teraz" za flagą, bez licznika) po pasku mediów */}
    {extra}
    {landing.sources.length > 0 && <div className="pt-nw__foot" id="pp-zrodla" tabIndex={-1}>
      <p className="pt-nw__note">Źródła w tym widoku:</p>
      <ul className="pt-nw__sources" aria-label="Źródła danych w tym widoku">
        {landing.sources.map(s => <li key={`${s.label}-${s.url}`}><a href={s.url ?? '#'} target={s.url?.startsWith('/') ? undefined : '_blank'} rel="noopener noreferrer">{s.label}<i aria-hidden="true"> ↗</i></a></li>)}
      </ul>
    </div>}
  </section>;
}
