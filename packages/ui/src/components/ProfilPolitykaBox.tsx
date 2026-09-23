"use client";

import { useId, useState } from 'react';
import {
  DEMO_POLITICIAN,
  DEMO_REGISTRY,
  DEMO_VOTES,
  ENTITY_KIND_LABELS,
  VERIFICATION_LABELS,
  VOTE_LABELS,
  type DemoRegistryRelation,
  type DemoVote,
  type EntityKind,
} from '../lib/powiekszonyBoxDemo';

type StatusFilter = 'all' | 'obecna' | 'historyczna';

const ENTITY_ORDER: EntityKind[] = ['fundacja', 'stowarzyszenie', 'spolka'];
const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'Wszystkie' },
  { value: 'obecna', label: 'Obecne' },
  { value: 'historyczna', label: 'Historyczne' },
];

const dateFormat = new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'short', year: 'numeric' });
/** Daty bez godziny interpretujemy w południe czasu polskiego, żeby uniknąć przesunięcia doby. */
const formatDay = (date: string) => dateFormat.format(new Date(`${date}T12:00:00+02:00`));

function RelationRow({ relation }: { relation: DemoRegistryRelation }) {
  return (
    <li className={`mvp-xprof-relation is-${relation.verification}`}>
      <div className="mvp-xprof-relation-main">
        <strong>{relation.entity}</strong>
        <span className={`mvp-xprof-verification is-${relation.verification}`}>
          <span aria-hidden="true">{relation.verification === 'potwierdzone' ? '✓' : '?'}</span> {VERIFICATION_LABELS[relation.verification]}
        </span>
      </div>
      <dl>
        <div><dt>Rodzaj</dt><dd>{ENTITY_KIND_LABELS[relation.kind].singular}</dd></div>
        <div><dt>Publiczna rola</dt><dd>{relation.publicRole}</dd></div>
        <div><dt>Relacja</dt><dd><span className={`mvp-xprof-status is-${relation.status}`}>{relation.status === 'obecna' ? 'obecna' : 'historyczna'}</span></dd></div>
        <div><dt>Weryfikacja</dt><dd><time dateTime={relation.verifiedAt}>{formatDay(relation.verifiedAt)}</time></dd></div>
        <div><dt>Źródło</dt><dd>{relation.sourceLabel} <small>(demo — link nieaktywny)</small></dd></div>
      </dl>
    </li>
  );
}

function VoteRow({ vote }: { vote: DemoVote }) {
  return (
    <tr>
      <td data-label="Data"><time dateTime={vote.date}>{formatDay(vote.date)}</time></td>
      <th scope="row" data-label="Temat">{vote.topic}</th>
      <td data-label="Głos"><span className={`mvp-xprof-vote is-${vote.choice}`}>{VOTE_LABELS[vote.choice]}</span></td>
      <td data-label="Źródło">{vote.sourceLabel} <small>(link nieaktywny)</small></td>
    </tr>
  );
}

export function ProfilPolitykaBox({ titleId, person = DEMO_POLITICIAN, votes = DEMO_VOTES, registry = DEMO_REGISTRY }: {
  titleId: string;
  person?: typeof DEMO_POLITICIAN;
  votes?: DemoVote[];
  registry?: DemoRegistryRelation[];
}) {
  const uid = useId();
  const [status, setStatus] = useState<StatusFilter>('all');
  const shown = registry.filter(relation => status === 'all' || relation.status === status);
  const pending = registry.filter(relation => relation.verification === 'do-potwierdzenia').length;
  const sortedVotes = [...votes].sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div className="mvp-xbox mvp-xprof">
      <header className="mvp-xbox-head">
        <p className="mvp-xbox-meta">
          <span className="mvp-xbox-type">PROFIL</span>
          <span>{person.fictionalNote} · dane demonstracyjne</span>
        </p>
        <h2 id={titleId} tabIndex={-1}>{person.name} <small>({person.fictionalNote})</small></h2>
        <p className="mvp-xbox-byline">{person.publicRole} · {person.club}</p>
        <p className="mvp-xbox-desc">{person.description}</p>
        <p className="mvp-xbox-link">Źródło profilu: <span className="mvp-xbox-url">{person.url}</span> <small>(demo — link nieaktywny)</small></p>
      </header>

      <dl className="mvp-xprof-summary" aria-label="Podsumowanie profilu">
        <div><dt>Głosowania</dt><dd>{votes.length}</dd></div>
        {ENTITY_ORDER.map(kind => (
          <div key={kind}><dt>{ENTITY_KIND_LABELS[kind].plural}</dt><dd>{registry.filter(relation => relation.kind === kind).length}</dd></div>
        ))}
        <div><dt>Wymaga potwierdzenia</dt><dd>{pending}</dd></div>
      </dl>

      <section className="mvp-xprof-section" aria-labelledby={`${uid}-votes`}>
        <h3 id={`${uid}-votes`}>Głosowania <span>ostatnie jawne głosowania · krótki temat zamiast technicznej nazwy posiedzenia</span></h3>
        <table className="mvp-xprof-votes">
          <caption className="sr-only">Głosowania: data, temat, głos i źródło</caption>
          <thead>
            <tr><th scope="col">Data</th><th scope="col">Temat głosowania</th><th scope="col">Głos</th><th scope="col">Źródło</th></tr>
          </thead>
          <tbody>
            {sortedVotes.map(vote => <VoteRow key={vote.id} vote={vote} />)}
          </tbody>
        </table>
      </section>

      <section className="mvp-xprof-section" aria-labelledby={`${uid}-registry`}>
        <div className="mvp-xprof-section-head">
          <h3 id={`${uid}-registry`}>Podmioty w rejestrach <span>publiczne funkcje w organizacjach i spółkach</span></h3>
          <div className="mvp-xbox-counters mvp-xprof-status-filter" role="group" aria-label="Pokaż relacje">
            {STATUS_FILTERS.map(option => (
              <button key={option.value} type="button" aria-pressed={status === option.value} onClick={() => setStatus(option.value)}>
                <span>{option.label}</span>
              </button>
            ))}
          </div>
        </div>
        <p className="mvp-xprof-note">
          Pokazujemy tylko nazwę podmiotu, rodzaj, publiczną rolę, status relacji, datę weryfikacji i źródło. Bez adresów, numerów PESEL, dat urodzenia i danych osób prywatnych. Relacja nie jest oceną osoby.
        </p>
        {ENTITY_ORDER.map(kind => {
          const items = shown.filter(relation => relation.kind === kind);
          return (
            <section key={kind} className="mvp-xprof-group" aria-labelledby={`${uid}-${kind}`}>
              <h4 id={`${uid}-${kind}`}>{ENTITY_KIND_LABELS[kind].plural} <span>{items.length}</span></h4>
              {items.length ? (
                <ul>{items.map(relation => <RelationRow key={relation.id} relation={relation} />)}</ul>
              ) : (
                <p className="mvp-xbox-empty">Brak relacji dla wybranego filtra.</p>
              )}
            </section>
          );
        })}
      </section>

      <p className="mvp-xbox-disclaimer">
        Etykieta „wymaga potwierdzenia redakcji” oznacza, że relacja nie została jeszcze sprawdzona w źródle publicznym. Profil nie zawiera automatycznej oceny osoby.
      </p>
    </div>
  );
}
