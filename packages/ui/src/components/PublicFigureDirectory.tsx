"use client";

import { FORMS, plural } from "../lib/plural";
import { XAccountSuggest } from "./clinic/XAccountSuggest";
import { useEffect, useId, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { DataExport } from './DataExport';
import { ApiError } from '../lib/api';
import {
  ROLE_CATEGORY_LABELS,
  usePublicFigure,
  usePublicFigures,
  type PublicFigureRoleCategory,
} from '../lib/publicFigures';
import { PublicFigureProfile } from './PublicFigureProfile';
import { Breadcrumbs, Button, Dropdown, SearchField, SectionHeader } from '../kit';

const notFound = (error: unknown) => error instanceof ApiError && (error.status === 404 || error.status === 405);

/** Pełny profil pod /osoby-publiczne/[id] — dane wyłącznie z GET /api/public-figures/:id/. */
export function PublicFigurePage({ id }: { id: number }) {
  const figure = usePublicFigure(id);
  useEffect(() => { if (figure.data) document.title = `${figure.data.name} — profil publiczny · spin.clinic`; }, [figure.data]);
  if (figure.isPending) return <p role="status" className="sc-public-figure__hint sc-public-figure-page">Ładuję profil…</p>;
  if (figure.isError) {
    return (
      <section className="sc-public-figure sc-public-figure-page">
        <p className="sc-public-figure-kicker">OSOBA PUBLICZNA</p>
        <h1>{notFound(figure.error) ? 'Nie znaleziono profilu' : 'Nie udało się pobrać profilu'}</h1>
        <p className="sc-public-figure-neutral">{notFound(figure.error) ? 'Profil nie istnieje, został zarchiwizowany albo rejestr osób publicznych nie jest jeszcze dostępny na tym serwerze.' : 'Spróbuj ponownie za chwilę.'}</p>
        <p className="sc-public-figure-links"><Link href="/osoby-publiczne">← Osoby publiczne</Link></p>
      </section>
    );
  }
  return (
    <div className="sc-public-figure-page">
      <Breadcrumbs items={[{ label: "Główna", href: "/" }, { label: "Osoby publiczne", href: "/osoby-publiczne" }, { label: figure.data.name }]} />
      <PublicFigureProfile figure={figure.data} />
    </div>
  );
}

const SORT_LABELS: Record<string, string> = { name: 'Po nazwisku (A–Z)', diagnoses: 'Najwięcej diagnoz Dr. Spina' };

/** Lista /osoby-publiczne — dane z GET /api/public-figures/; filtry i strona żyją w adresie (?q=&role_category=&party=&chamber=&sort=&page=). */
export function PublicFigureDirectory() {
  const uid = useId();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.get('q') ?? '';
  const role = (searchParams.get('role_category') ?? '') as PublicFigureRoleCategory | '';
  const party = searchParams.get('party') ?? '';
  const chamber = searchParams.get('chamber') ?? '';
  const sort = searchParams.get('sort') === 'diagnoses' ? 'diagnoses' : '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const [input, setInput] = useState(query);
  useEffect(() => setInput(query), [query]);
  const list = usePublicFigures(query, role, page, { party, chamber, sort });
  const rows = list.data?.results ?? [];
  const facets = list.data?.facets;

  function update(values: Record<string, string>, keepPage = false) {
    const next = new URLSearchParams(searchParams.toString());
    Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    if (!keepPage) next.delete('page');
    router.replace(`${pathname}${next.size ? `?${next}` : ''}`, { scroll: false });
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); update({ q: input.trim() }); }
  const partyLabel = (code: string) => facets?.parties.find(item => item.code === code)?.short ?? code;
  const chips: Array<{ label: string; clear: Record<string, string> }> = [];
  if (query) chips.push({ label: `Szukaj: ${query}`, clear: { q: '' } });
  if (role) chips.push({ label: ROLE_CATEGORY_LABELS[role] ?? role, clear: { role_category: '' } });
  if (party) chips.push({ label: `Klub: ${partyLabel(party)}`, clear: { party: '' } });
  if (chamber) chips.push({ label: facets?.chambers.find(item => item.code === chamber)?.label ?? chamber, clear: { chamber: '' } });
  if (sort) chips.push({ label: SORT_LABELS.diagnoses, clear: { sort: '' } });

  return (
    <section className="sc-public-directory" aria-labelledby={`${uid}-title`}>
      <SectionHeader variant="page" kicker="REJESTR" titleId={`${uid}-title`} title="Osoby publiczne"
        subtitle="Profile pokazują funkcję publiczną, oficjalne głosowania i relacje potwierdzone w publicznych źródłach. Zespół spin.clinic dodaje osoby ręcznie, z linkiem do źródła funkcji." />
      <details className="sc-criteria">
        <summary>Jak wybieramy osoby</summary>
        <ul>
          <li>Dodajemy osoby, które pełnią funkcję publiczną: w rządzie i administracji, w parlamencie (Sejm, Senat, Parlament Europejski), w samorządzie albo kierują partią lub klubem parlamentarnym.</li>
          <li>Każdy profil wymaga linku do oficjalnego źródła funkcji; dane o funkcjach w fundacjach, stowarzyszeniach i spółkach pochodzą z KRS i są danymi rejestrowymi, bez oceny.</li>
          <li>Konto X podpinamy dopiero po potwierdzeniu oficjalnym dowodem. Nie wystawiamy ocen osób.</li>
          <li>Domyślnie lista jest posortowana po nazwisku (alfabet polski); możesz posortować ją po liczbie diagnoz. Klub i izbę bierzemy z oficjalnego rejestru mandatów. Brakuje kogoś albo dane są błędne? Otwórz profil i użyj „Zgłoś błąd lub sprzeciw”.</li>
        </ul>
      </details>
      <form className="sc-public-directory__filters" role="search" onSubmit={submit}>
        <SearchField id={`${uid}-q`} label="Imię, funkcja lub instytucja" value={input} onChange={setInput} maxLength={120} placeholder="Imię, funkcja lub instytucja" />
        <Dropdown label="Rodzaj funkcji" ariaLabel="Rodzaj funkcji" mode="single" presentation="auto" value={role} onChange={value => update({ role_category: String(value) })}
          items={[{ value: '', label: 'Wszystkie' }, ...Object.entries(ROLE_CATEGORY_LABELS).map(([value, label]) => ({ value, label }))]} />
        <Dropdown label="Klub lub partia" ariaLabel="Klub lub partia" mode="single" presentation="auto" value={party} onChange={value => update({ party: String(value) })}
          items={[{ value: '', label: 'Wszystkie' }, ...(party && !facets?.parties.some(item => item.code === party) ? [{ value: party, label: party }] : []),
            ...(facets?.parties ?? []).map(item => ({ value: item.code, label: `${item.short} (${item.count})` }))]} />
        <Dropdown label="Izba" ariaLabel="Izba" mode="single" presentation="auto" value={chamber} onChange={value => update({ chamber: String(value) })}
          items={[{ value: '', label: 'Wszystkie' }, ...(chamber && !facets?.chambers.some(item => item.code === chamber) ? [{ value: chamber, label: chamber }] : []),
            ...(facets?.chambers ?? []).map(item => ({ value: item.code, label: `${item.label} (${item.count})` }))]} />
        <Dropdown label="Sortowanie" ariaLabel="Sortowanie" mode="single" presentation="auto" value={sort || 'name'} onChange={value => update({ sort: value === 'diagnoses' ? 'diagnoses' : '' })}
          items={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))} />
        <Button type="submit" variant="primary">Szukaj</Button>
      </form>
      {chips.length ? <div className="sc-clinic-db__active" aria-label="Aktywne filtry">
        {chips.map(chip => <button key={Object.keys(chip.clear).join('-')} type="button" aria-label={`Usuń filtr: ${chip.label}`} onClick={() => update(chip.clear)}>{chip.label} <span aria-hidden="true">×</span></button>)}
        <button type="button" className="sc-clinic-db__clear-all" onClick={() => router.replace(pathname, { scroll: false })}>Wyczyść wszystko</button>
      </div> : null}

      <p className="sc-t-meta sc-text-2" role="status">{list.data ? `Wyświetlono ${rows.length ? (list.data.page - 1) * list.data.page_size + 1 : 0}–${rows.length ? (list.data.page - 1) * list.data.page_size + rows.length : 0} z ${list.data.count} ${list.data.count === 1 ? "osoby" : "osób"} dla wybranych filtrów. ` : ''}Pokazujemy wyłącznie profile oparte na danych z rejestru; rejestr nie obejmuje wszystkich osób publicznych.</p>
      <DataExport dataset="osoby" params={{ q: query, role_category: role, party, chamber, sort }} />
      {list.data && (page > 1 || list.data.count > list.data.page_size) && <nav className="sc-directory-pagination" aria-label="Strony rejestru osób">
        <Button disabled={page === 1 || list.isFetching} onClick={() => update({ page: String(page - 1) }, true)}>Poprzednia</Button>
        <span>Strona {page}</span>
        <Button disabled={!list.data || list.isFetching || page * list.data.page_size >= list.data.count} onClick={() => update({ page: String(page + 1) }, true)}>Następna</Button>
      </nav>}
      {list.isPending && <p role="status" className="sc-t-body sc-text-2">Ładuję rejestr…</p>}
      {list.isError && (
        <p className="sc-t-body sc-text-2">
          {notFound(list.error) ? 'Rejestr osób publicznych nie jest jeszcze dostępny na tym serwerze.' : 'Nie udało się pobrać rejestru.'}
        </p>
      )}
      {list.isSuccess && !rows.length && <p className="sc-t-body sc-text-2">Brak osób dla wybranych filtrów.</p>}
      {rows.length > 0 && (
        <ul className="sc-public-directory__list">
          {rows.map(row => (
            <li key={row.id}>
              <div>
                <Link href={`/osoby-publiczne/${row.id}`} className="sc-public-directory__name">{row.name}</Link>
                <p className="sc-t-body"><span className="sc-public-figure-status" data-status={row.status}>{row.status === 'current' ? 'Obecna funkcja' : 'Była funkcja'}</span>{row.role_title}{row.organisation && !row.role_title.toLowerCase().includes(row.organisation.toLowerCase()) && ` · ${row.organisation}`}</p>
                <p className="sc-public-directory__meta">
                  {row.party ? <span className="sc-public-directory__party" title={row.party.name}>{row.party.short}</span> : null}
                  {row.chamber ? <span>{facets?.chambers.find(item => item.code === row.chamber)?.label ?? row.chamber}</span> : null}
                  <span>{row.has_x_account ? `${row.diagnoses_count ?? 0} ${plural(row.diagnoses_count ?? 0, FORMS.diagnosis)} Dr. Spina` : 'brak diagnoz: konto X niepotwierdzone'}</span>
                </p>
                <p className="sc-public-directory__x">{row.has_x_account ? <span className="sc-x-badge" title="Konto X potwierdzone oficjalnym dowodem — wpisy z tego konta analizujemy w Klinice">Konto X: obserwujemy</span> : <><span className="sc-x-badge sc-x-badge--none">X · brak potwierdzonego konta w bazie</span><XAccountSuggest figureId={row.id} name={row.name} /></>}</p>
              </div>
              <span className="sc-public-directory__go" aria-hidden="true">Zobacz profil →</span>
            </li>
          ))}
        </ul>
      )}

    </section>
  );
}
