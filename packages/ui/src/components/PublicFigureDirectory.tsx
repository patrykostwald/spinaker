"use client";

import { useEffect, useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { ApiError } from '../lib/api';
import {
  ORGANISATION_KIND_LABELS,
  ROLE_CATEGORY_LABELS,
  usePublicFigure,
  usePublicFigures,
  type PublicFigureRoleCategory,
  type PublicFigureSummary,
} from '../lib/publicFigures';
import { Dialog } from './Dialog';
import { PublicFigureProfile } from './PublicFigureProfile';
import { Button, Dropdown, SearchField } from '../kit';

const notFound = (error: unknown) => error instanceof ApiError && (error.status === 404 || error.status === 405);

/** Pełny profil pod /osoby-publiczne/[id] — dane wyłącznie z GET /api/public-figures/:id/. */
export function PublicFigurePage({ id }: { id: number }) {
  const figure = usePublicFigure(id);
  useEffect(() => { if (figure.data) document.title = `${figure.data.name} — profil publiczny · spin.clinic`; }, [figure.data]);
  if (figure.isPending) return <p role="status" className="mvp-pf-hint mvp-pf-page">Ładuję profil…</p>;
  if (figure.isError) {
    return (
      <section className="mvp-pf mvp-pf-page">
        <p className="mvp-pf-kicker">OSOBA PUBLICZNA</p>
        <h1>{notFound(figure.error) ? 'Nie znaleziono profilu' : 'Nie udało się pobrać profilu'}</h1>
        <p className="mvp-pf-neutral">{notFound(figure.error) ? 'Profil nie istnieje, został zarchiwizowany albo rejestr osób publicznych nie jest jeszcze dostępny na tym serwerze.' : 'Spróbuj ponownie za chwilę.'}</p>
        <p className="mvp-pf-links"><Link href="/osoby-publiczne">← Osoby publiczne</Link></p>
      </section>
    );
  }
  return (
    <div className="mvp-pf-page">
      <p className="mvp-pf-back"><Link href="/osoby-publiczne">← Osoby publiczne</Link></p>
      <PublicFigureProfile figure={figure.data} />
    </div>
  );
}

/** Podgląd w oknie: nagłówek i liczniki, bez materiałów. Pełny profil — osobna trasa. */
function FigurePreview({ summary }: { summary: PublicFigureSummary }) {
  const detail = usePublicFigure(summary.id);
  const organisations = detail.data?.organisations ?? [];
  return (
    <div className="mvp-pf-preview">
      <p className="mvp-pf-kicker">{ROLE_CATEGORY_LABELS[summary.role_category] ?? 'Osoba publiczna'}</p>
      <h2>{summary.name}</h2>
      <p className="mvp-pf-role"><span className={`mvp-pf-status is-${summary.status}`}>{summary.status === 'current' ? 'Aktualna funkcja' : 'Była funkcja'}</span>{summary.role_title}{summary.organisation && ` · ${summary.organisation}`}</p>
      {detail.isPending && <p role="status" className="mvp-pf-hint">Ładuję głosowania i relacje…</p>}
      {detail.isError && <p className="mvp-pf-neutral">Szczegóły profilu nie są jeszcze dostępne na tym serwerze.</p>}
      {detail.data && (
        <dl className="mvp-pf-preview-facts">
          <div><dt>Głosowania</dt><dd>{detail.data.votes.available ? detail.data.votes.results.length : 'brak jeszcze ręcznie potwierdzonego połączenia z mandatem'}</dd></div>
          {(['foundation', 'association', 'company'] as const).map(kind => (
            <div key={kind}><dt>{ORGANISATION_KIND_LABELS[kind].plural}</dt><dd>{organisations.filter(item => item.kind === kind).length || 'brak jeszcze ręcznie potwierdzonego połączenia'}</dd></div>
          ))}
        </dl>
      )}
      <p className="mvp-pf-links"><Link href={`/osoby-publiczne/${summary.id}`} className="mvp-pf-primary">Otwórz pełny profil →</Link></p>
    </div>
  );
}

/** Lista /osoby-publiczne — dane z GET /api/public-figures/?q=&role_category=. */
export function PublicFigureDirectory() {
  const uid = useId();
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const [role, setRole] = useState<PublicFigureRoleCategory | ''>('');
  const [preview, setPreview] = useState<PublicFigureSummary | null>(null);
  const list = usePublicFigures(query, role);
  const rows = list.data?.results ?? [];

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setQuery(input.trim()); }

  return (
    <section className="mvp-pf mvp-pf-page" aria-labelledby={`${uid}-title`}>
      <header className="mvp-pf-head">
        <p className="mvp-pf-kicker">REJESTR REDAKCYJNY</p>
        <h1 id={`${uid}-title`}>Osoby publiczne</h1>
        <p className="mvp-pf-lead">Profile pokazują funkcję publiczną, oficjalne głosowania i relacje potwierdzone w publicznych źródłach. Redakcja dodaje osoby ręcznie, z linkiem do źródła funkcji.</p>
      </header>
      <form className="sc-public-directory__filters" role="search" onSubmit={submit}>
        <SearchField id={`${uid}-q`} label="Imię, funkcja lub instytucja" value={input} onChange={setInput} maxLength={120} placeholder="Imię, funkcja lub instytucja" />
        <Dropdown label="Rodzaj funkcji" ariaLabel="Rodzaj funkcji" mode="single" presentation="auto" value={role} onChange={value => setRole(value as PublicFigureRoleCategory | '')}
          items={[{ value: '', label: 'Wszystkie' }, ...Object.entries(ROLE_CATEGORY_LABELS).map(([value, label]) => ({ value, label }))]} />
        <Button type="submit" variant="primary">Szukaj</Button>
      </form>

      {list.isPending && <p role="status" className="mvp-pf-hint">Ładuję rejestr…</p>}
      {list.isError && (
        <p className="mvp-pf-neutral">
          {notFound(list.error) ? 'Rejestr osób publicznych nie jest jeszcze dostępny na tym serwerze.' : 'Nie udało się pobrać rejestru.'}
        </p>
      )}
      {list.isSuccess && !rows.length && <p className="mvp-pf-neutral">Brak osób dla wybranych filtrów.</p>}
      {rows.length > 0 && (
        <ul className="mvp-pf-list">
          {rows.map(row => (
            <li key={row.id}>
              <div>
                <Link href={`/osoby-publiczne/${row.id}`} className="mvp-pf-list-name">{row.name}</Link>
                <p className="mvp-pf-role"><span className={`mvp-pf-status is-${row.status}`}>{row.status === 'current' ? 'Aktualna' : 'Była'}</span>{row.role_title}{row.organisation && ` · ${row.organisation}`}</p>
              </div>
              <Button type="button" variant="quiet" aria-haspopup="dialog" onClick={() => setPreview(row)}>Podgląd<span className="sr-only"> profilu {row.name}</span></Button>
            </li>
          ))}
        </ul>
      )}
      <p className="mvp-pf-hint">Lista zawiera najwyżej 100 osób. Pokazujemy wyłącznie profile oparte na danych z rejestru.</p>
      <Dialog open={preview !== null} onClose={() => setPreview(null)} title={preview ? `Podgląd profilu: ${preview.name}` : 'Podgląd profilu'} className="mvp-pf-dialog">
        {preview && <FigurePreview key={preview.id} summary={preview} />}
      </Dialog>
    </section>
  );
}
