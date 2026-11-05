"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortalConfig, sourceDirectory, directoryGroup, channelIdentity, suggestSource } from '@spin-clinic/ui';
import type { Source } from '@spin-clinic/ui';
import { ArchiveProgress } from '@spin-clinic/ui';
import { FORMS, plural } from '@spin-clinic/ui';
import { Button, InfoPage, SearchField, SectionHeader } from '@spin-clinic/ui/kit';
import { DataExport } from '@spin-clinic/ui';

/** Znaczki przy źródle: co już mamy (zgoda / dane publiczne, YouTube, X), a na co czekamy. */
function SourceChannels({ source }: { source: Source }) {
  const identity = channelIdentity(source.url);
  const channelOnly = Boolean(identity);
  const xHandle = source.x_handle || (identity?.startsWith('x:') ? identity.slice(3) : '');
  const youtube = identity?.startsWith('youtube:') ? source.url : source.youtube_url;
  return <small className="sc-source-chips">
    {channelOnly ? null : source.access === 'approved'
      ? <span className="sc-source-chip is-on" title="Zgoda wydawcy albo dane publiczne na jawnych zasadach">Zgoda</span>
      : <span className="sc-source-chip" title="Czekamy na zgodę wydawcy">weryfikacja</span>}
    {youtube ? <a className="sc-source-chip is-on" href={youtube} target="_blank" rel="noopener noreferrer" aria-label={`${source.name} na YouTube`}>YouTube</a> : null}
    {xHandle ? <a className="sc-source-chip is-on" href={`https://x.com/${xHandle}`} target="_blank" rel="noopener noreferrer" aria-label={`${source.name} na X (@${xHandle})`}>X</a> : null}
  </small>;
}

/** Status wiersza z dwóch niezależnych faktów: czy źródło jest aktywne i czy ma zgodę (ta sama reguła co plakietka). */
function rowStatus(source: Source, members: Source[]) {
  const channelOnly = Boolean(channelIdentity(source.url));
  const active = members.some(member => member.is_active);
  const awaitingConsent = !channelOnly && source.access !== 'approved';
  const caption = active
    ? awaitingConsent ? 'Aktywne · zgoda w weryfikacji' : 'Aktywne źródło / kanał'
    : awaitingConsent ? 'Nieaktywne · czeka na zgodę / weryfikację' : 'Nieaktywne';
  return { awaitingConsent, caption };
}

export default function SourcesPage() {
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig });
  const [search, setSearch] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState('');
  const [sendError, setSendError] = useState('');
  const [status, setStatus] = useState('all');
  const [limits, setLimits] = useState({ top: 30, media: 30, publiczne: 30 });
  const allGroups = useMemo(() => sourceDirectory(config.data?.sources ?? []), [config.data?.sources]);
  const visible = useMemo(() => allGroups.filter(group =>
    group.members.some(source => [source.name, source.url].join(' ').toLocaleLowerCase('pl').includes(search.trim().toLocaleLowerCase('pl')))
    && (status === 'all' || (status === 'active' ? group.members.some(source => source.is_active === true) : rowStatus(group.source, group.members).awaitingConsent))
  ), [allGroups, search, status]);
  const groups = {
    top: visible.filter(group => directoryGroup(group.source) === 'top'),
    media: visible.filter(group => directoryGroup(group.source) === 'media'),
    publiczne: visible.filter(group => directoryGroup(group.source) === 'publiczne'),
  };
  function resetLimits() { setLimits({ top: 30, media: 30, publiczne: 30 }); }
  const stats = config.data?.source_stats;

  async function suggest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending) return;
    if (!suggestion.trim()) { setSent(''); setSendError('Wpisz adres strony, którą warto sprawdzić.'); return; }
    setSending(true); setSendError(''); setSent('');
    try {
      const result = await suggestSource(suggestion.trim());
      setSent(result.status === 'received'
        ? `Dziękujemy. Sprawdzimy ${result.host} przed dodaniem do katalogu.`
        : `Ten adres (${result.host}) już czeka na sprawdzenie. Dziękujemy.`);
      setSuggestion('');
    } catch (reason) {
      setSendError(reason instanceof Error ? reason.message : 'Nie udało się wysłać sugestii.');
    } finally { setSending(false); }
  }

  return <InfoPage className="sc-source-page" eyebrow="KATALOG" title="Źródła"
    lead="Źródła wiadomości: aktywne oraz kandydatury czekające na weryfikację kanału i zasad wykorzystania. Dowody do konkretnej diagnozy znajdziesz przy jej twierdzeniach.">
    <details className="sc-criteria">
      <summary>Jak wybieramy źródła</summary>
      <ul>
        <li>Wpisujemy źródła publiczne i jawne: portale informacyjne, instytucje publiczne oraz oficjalne kanały YouTube i konta X osób publicznych. Korzystamy tylko z legalnych dróg: zgody wydawcy, publicznych interfejsów (API) i danych udostępnionych na jawnych zasadach.</li>
        <li>Z każdego źródła pobieramy tytuł, datę i link do oryginału; nie przedrukowujemy pełnych tekstów. Zawsze odsyłamy do strony źródła.</li>
        <li>Źródło trafia do katalogu po sprawdzeniu kanału i zasad wykorzystania. Kolejność na liście nie jest oceną wiarygodności ani rankingiem.</li>
        <li>Podział na obozy (rząd i opozycja) dotyczy autora wpisu, a nie źródła: źródła nie oceniamy ani nie szeregujemy. Brakuje ważnego źródła? Zaproponuj je na dole strony.</li>
      </ul>
    </details>
    <dl className="sc-source-page__stats">
      <div><dt>W katalogu</dt><dd>{stats?.catalog_total ?? '—'}</dd></div>
      <div><dt>Aktywne (w tym kanały)</dt><dd>{stats?.active ?? '—'}</dd></div>
      <div><dt>Czeka na zgodę / weryfikację</dt><dd>{config.data ? allGroups.filter(({ source, members }) => rowStatus(source, members).awaitingConsent).length : '—'}</dd></div>
    </dl>
    <SearchField className="sc-source-page__search" label="Znajdź źródło" value={search} onChange={value => { setSearch(value); resetLimits(); }} placeholder="Nazwa źródła" />
    <label className="sc-source-directory-filter">Status źródła<select value={status} onChange={event => { setStatus(event.target.value); resetLimits(); }}>
      <option value="all">Wszystkie</option><option value="active">Aktywne</option><option value="pending">Oczekujące na zgodę / weryfikację</option>
    </select></label>
    <p className="sc-t-meta sc-text-2 sc-source-page__note">Liczniki powyżej liczą osobno źródła i ich kanały (strona, YouTube, X), dlatego jest ich więcej niż wierszy na liście: lista łączy serwis z kanałami tylko na podstawie potwierdzonego powiązania. „Aktywne” obejmuje kanały, z których teraz pobieramy wpisy. Aktywność i zgoda to odrębne informacje. Stan na {new Date().toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })}.</p>
    <DataExport dataset="zrodla" params={{ q: search.trim(), status: status === 'all' ? '' : status }} />
    {config.isPending && <p role="status">Ładuję katalog…</p>}
    {config.isError && <div role="alert"><p>Nie udało się pobrać katalogu.</p><Button onClick={() => config.refetch()}>Spróbuj ponownie</Button></div>}
    <ul className="sc-source-legend" aria-label="Oznaczenia">
      <li><span className="sc-source-chip is-on">Zgoda</span> potwierdzona zgoda wydawcy albo dane publiczne (np. publiczne API) na jawnych zasadach</li>
      <li><span className="sc-source-chip is-on">YouTube</span> <span className="sc-source-chip is-on" role="img" aria-label="konto X">X</span> oficjalny kanał i konto, podlinkowane na stronie źródła</li>
      <li><span className="sc-source-chip">weryfikacja</span> w toku: czekamy na zgodę albo potwierdzenie kanału</li>
      <li><span className="sc-source-chip">Nieaktywne</span> wyłączone: źródło lub kanał jest w katalogu, ale nic z niego nie pobieramy</li>
    </ul>
    <div className="sc-source-page__grid">
      {([['top', 'Wybrane media'], ['media', 'Media'], ['publiczne', 'Instytucje publiczne']] as const).map(([key, label]) => <section key={key}>
        <SectionHeader title={label} meta={`${groups[key].length} ${plural(groups[key].length, FORMS.record)}`} />
        <p role="status" className="sc-t-caption">Wyświetlono {Math.min(limits[key], groups[key].length)} z {groups[key].length}</p>
        <ul>{groups[key].slice(0, limits[key]).map(({source, members}) => <li key={source.id}>
          <span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}</span>
          <SourceChannels source={source} />
          <small>{rowStatus(source, members).caption}</small>
        </li>)}</ul>
        {limits[key] < groups[key].length && <Button onClick={() => setLimits(previous => ({...previous, [key]: previous[key] + 30}))}>Pokaż więcej<span className="sr-only">: {label}</span></Button>}
        {!groups[key].length && config.isSuccess && <p>Brak źródeł dla wybranych filtrów.</p>}
      </section>)}
    </div>
    <section className="sc-source-page__progress"><p>POSTĘP KATALOGU</p><h2>Jak rozwija się baza źródeł?</h2><ArchiveProgress /></section>
    <section className="sc-source-page__suggestion"><p>ROZBUDOWA BAZY</p><h2>Zaproponuj źródło</h2><p>Podaj adres strony, którą warto sprawdzić. Każde źródło weryfikujemy przed uruchomieniem.</p>
      <form className="sc-search-form" onSubmit={suggest}><SearchField label="Adres proponowanego źródła" value={suggestion} onChange={setSuggestion} placeholder="https://…" inputType="url" required maxLength={300} /><Button type="submit" variant="primary" loading={sending} disabled={sending}>Wyślij sugestię</Button></form>
      {sent ? <p role="status" className="sc-t-meta sc-text-2">{sent}</p> : null}
      {sendError ? <p role="alert" className="sc-t-meta sc-text-2">{sendError}</p> : null}
    </section>
  </InfoPage>;
}
