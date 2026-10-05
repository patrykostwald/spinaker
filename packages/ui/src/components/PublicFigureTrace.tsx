"use client";

import { useId, type ReactNode } from 'react';
import { usePublicFigureTrace, type PublicFigureTrace as Trace } from '../lib/publicFigures';

/*
 * „Ślad w dokumentach” - bezpłatny wycinek profilu przeszłość.today na profilu spin.clinic:
 * 5 ostatnich głosowań (głos wobec większości klubu), 3 ostatnie interpelacje lub zapytania, liczby z 12 miesięcy
 * i jeden odnośnik do pełnego profilu. KRS, Wspólne mianowniki, alerty i eksport zostają w przeszłość.today.
 * Laws of UX: Common Region (trzy boksy jednej grupy), Von Restorff (wyróżniony tylko głos inny niż klub), Fitts (cele 44 px).
 */

const dateFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'short', year: 'numeric' });
const day = (iso: string | null) => (iso ? dateFormat.format(new Date(iso)) : 'bez daty');

function plural(count: number, one: string, few: string, many: string) {
  const tens = count % 100;
  const units = count % 10;
  if (count === 1) return one;
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
  return many;
}

function External({ href, className, title, children }: { href: string; className?: string; title?: string; children: ReactNode }) {
  if (!/^https?:\/\//i.test(href)) return <span className={className} title={title}>{children}</span>;
  return <a href={href} className={className} title={title} target="_blank" rel="noopener noreferrer">{children}<span className="sc-sr-only"> (otwiera się w nowej karcie)</span></a>;
}

function Votes({ uid, trace, onShowVotes }: { uid: string; trace: Trace; onShowVotes: () => void }) {
  return (
    <section className="sc-trace__box" aria-labelledby={`${uid}-votes`}>
      <h3 id={`${uid}-votes`}>Ostatnie głosowania</h3>
      {!trace.available ? <p className="sc-trace__empty">{trace.reason}</p>
        : !trace.votes.length ? <p className="sc-trace__empty">Brak głosowań tego mandatu w naszej Bazie.</p> : (
          <ol className="sc-trace__list">
            {trace.votes.map((vote, index) => (
              <li key={`${vote.url}-${index}`}>
                <External href={vote.url} className="sc-trace__title" title={vote.title}>{vote.title}</External>
                <span className="sc-trace__meta">
                  <time dateTime={vote.date ?? undefined}>{day(vote.date)}</time>
                  <span className="sc-trace__vote">{vote.vote}</span>
                  {vote.relation && <span className={`sc-trace__club${vote.relation === 'inaczej niż klub' ? ' is-different' : ''}`} title={vote.club_vote ? `Większość klubu ${vote.club}: ${vote.club_vote}` : undefined}>{vote.relation}{vote.club ? ` ${vote.club}` : ''}</span>}
                </span>
              </li>
            ))}
          </ol>
        )}
      <p className="sc-trace__foot">
        {trace.available ? <button type="button" className="sc-trace__link" onClick={onShowVotes}>Wszystkie głosowania</button> : <span>Źródło: Sejm RP</span>}
      </p>
    </section>
  );
}

function Documents({ uid, trace }: { uid: string; trace: Trace }) {
  return (
    <section className="sc-trace__box" aria-labelledby={`${uid}-docs`}>
      <h3 id={`${uid}-docs`}>Interpelacje i zapytania</h3>
      {!trace.available ? <p className="sc-trace__empty">Interpelacje i zapytania łączymy tylko z posłami przez oficjalny identyfikator Sejmu.</p>
        : !trace.documents.length ? <p className="sc-trace__empty">Brak interpelacji i zapytań tej osoby w naszej Bazie.</p> : (
          <ol className="sc-trace__list">
            {trace.documents.map(doc => (
              <li key={doc.url}>
                <External href={doc.url} className="sc-trace__title sc-trace__title--two">{doc.title || doc.label}</External>
                <span className="sc-trace__meta">
                  <time dateTime={doc.date ?? undefined}>{day(doc.date)}</time>
                  <span>{doc.label}</span>
                  {doc.answered !== null && <span>{doc.answered ? 'z odpowiedzią' : 'bez odpowiedzi'}</span>}
                </span>
              </li>
            ))}
          </ol>
        )}
      <p className="sc-trace__foot"><span>Źródło: oficjalne API Sejmu RP</span></p>
    </section>
  );
}

function Year({ uid, trace }: { uid: string; trace: Trace }) {
  const full = trace.full_profile;
  return (
    <section className="sc-trace__box" aria-labelledby={`${uid}-year`}>
      <h3 id={`${uid}-year`}>Ostatnie 12 miesięcy</h3>
      <div className="sc-trace__body">
        <dl className="sc-trace__numbers">
          <div><dt>{plural(trace.year.votes, 'głosowanie', 'głosowania', 'głosowań')}</dt><dd>{trace.year.votes}</dd></div>
          <div><dt>{plural(trace.year.documents, 'dokument Sejmu', 'dokumenty Sejmu', 'dokumentów Sejmu')}</dt><dd>{trace.year.documents}</dd></div>
        </dl>
        {full && (
          <div className="sc-trace__pro">
            <p>W pełnym profilu:</p>
            <ul>{full.features.map(feature => <li key={feature}>{feature}</li>)}</ul>
          </div>
        )}
      </div>
      <p className="sc-trace__foot">
        {full ? <External href={full.url} className="sc-trace__link sc-trace__cta">Pełny profil w przeszłość.today ↗</External> : <span>Ta sama miara dla wszystkich</span>}
      </p>
    </section>
  );
}

export function PublicFigureTrace({ figureId, onShowVotes }: { figureId: number; onShowVotes: () => void }) {
  const uid = useId();
  const trace = usePublicFigureTrace(figureId);
  if (trace.isError) return null;
  return (
    <section className="sc-trace" aria-labelledby={`${uid}-trace`} aria-busy={trace.isPending}>
      <header className="sc-trace__head">
        <h2 id={`${uid}-trace`}>Ślad w dokumentach</h2>
        <p>Oficjalne dane Sejmu RP, ta sama miara dla każdej osoby</p>
      </header>
      {trace.isPending ? <div className="sc-trace__grid sc-trace__grid--loading" role="status"><span className="sc-sr-only">Ładuję ślad w dokumentach</span></div> : (
        <div className="sc-trace__grid">
          <Votes uid={uid} trace={trace.data} onShowVotes={onShowVotes} />
          <Documents uid={uid} trace={trace.data} />
          <Year uid={uid} trace={trace.data} />
        </div>
      )}
    </section>
  );
}
