"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortalConfig, sourceDirectory, directoryGroup, channelIdentity } from '@spin-clinic/ui';
import type { Source } from '@spin-clinic/ui';
import { ArchiveProgress } from '@spin-clinic/ui';
import { Button, InfoPage, SearchField, SectionHeader } from '@spin-clinic/ui/kit';

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

export default function SourcesPage() {
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig });
  const [search, setSearch] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [status, setStatus] = useState('all');
  const [limits, setLimits] = useState({ top: 30, media: 30, publiczne: 30 });
  const visible = useMemo(() => sourceDirectory(config.data?.sources ?? []).filter(group =>
    group.members.some(source => [source.name, source.url].join(' ').toLocaleLowerCase('pl').includes(search.trim().toLocaleLowerCase('pl')))
    && (status === 'all' || group.members.some(source => status === 'active' ? source.is_active === true : source.access === 'pending'))
  ), [config.data?.sources, search, status]);
  const groups = {
    top: visible.filter(group => directoryGroup(group.source) === 'top'),
    media: visible.filter(group => directoryGroup(group.source) === 'media'),
    publiczne: visible.filter(group => directoryGroup(group.source) === 'publiczne'),
  };
  function resetLimits() { setLimits({ top: 30, media: 30, publiczne: 30 }); }
  const contact = process.env.NEXT_PUBLIC_CONTACT_EMAIL;
  const stats = config.data?.source_stats;

  function suggest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contact || !suggestion.trim()) return;
    window.location.href = `mailto:${contact}?subject=${encodeURIComponent('Sugestia źródła dla spin.clinic')}&body=${encodeURIComponent(`Proponowane źródło: ${suggestion.trim()}`)}`;
  }

  return <InfoPage className="sc-source-page" eyebrow="KATALOG" title="Źródła"
    lead="Źródła wiadomości: aktywne oraz kandydatury czekające na weryfikację kanału i zasad wykorzystania. Dowody do konkretnej diagnozy znajdziesz przy jej twierdzeniach.">
    <dl className="sc-source-page__stats">
      <div><dt>W katalogu</dt><dd>{stats?.catalog_total ?? '-'}</dd></div>
      <div><dt>Aktywne</dt><dd>{stats?.active ?? '-'}</dd></div>
      <div><dt>Oczekuje na odpowiedź</dt><dd>{stats?.awaiting_response ?? '-'}</dd></div>
    </dl>
    <section className="sc-source-page__suggestion"><p>ROZBUDOWA BAZY</p><h2>Zaproponuj źródło</h2><p>Podaj adres strony, którą warto sprawdzić. Każde źródło weryfikujemy przed uruchomieniem.</p>
      <form className="sc-search-form" onSubmit={suggest}><SearchField label="Adres proponowanego źródła" value={suggestion} onChange={setSuggestion} placeholder="https://…" inputType="url" required /><Button type="submit" variant="primary" disabled={!contact}>Wyślij sugestię</Button></form>
      {!contact && <small>Formularz połączymy ze skrzynką kontaktową po wskazaniu adresu kontaktowego.</small>}
    </section>
    <SearchField className="sc-source-page__search" label="Znajdź źródło" value={search} onChange={value => { setSearch(value); resetLimits(); }} placeholder="Nazwa źródła" />
    <label className="sc-source-directory-filter">Status źródła<select value={status} onChange={event => { setStatus(event.target.value); resetLimits(); }}>
      <option value="all">Wszystkie</option><option value="active">Aktywne</option><option value="pending">Oczekujące na zgodę / weryfikację</option>
    </select></label>
    <p className="sc-t-caption sc-text-2">Liczniki powyżej obejmują rekordy źródeł. Lista poniżej łączy serwis z kanałami tylko na podstawie potwierdzonego powiązania. Statusy dotyczą poszczególnych kanałów; aktywność i zgoda to odrębne informacje.</p>
    {config.isPending && <p role="status">Ładuję katalog…</p>}
    {config.isError && <div role="alert"><p>Nie udało się pobrać katalogu.</p><Button onClick={() => config.refetch()}>Spróbuj ponownie</Button></div>}
    <ul className="sc-source-legend" aria-label="Oznaczenia">
      <li><span className="sc-source-chip is-on">Zgoda</span> zgoda wydawcy albo dane publiczne na jawnych zasadach</li>
      <li><span className="sc-source-chip is-on">YouTube</span> <span className="sc-source-chip is-on">X</span> oficjalny kanał i konto, podlinkowane na stronie źródła</li>
      <li><span className="sc-source-chip">weryfikacja</span> czekamy na zgodę albo potwierdzenie kanału</li>
    </ul>
    <div className="sc-source-page__grid">
      {([['top', 'Wybrane media'], ['media', 'Media'], ['publiczne', 'Instytucje publiczne']] as const).map(([key, label]) => <section key={key}>
        <SectionHeader title={label} meta={`${groups[key].length} rekordów`} />
        <p role="status" className="sc-t-caption">Wyświetlono {Math.min(limits[key], groups[key].length)} z {groups[key].length}</p>
        <ul>{groups[key].slice(0, limits[key]).map(({source, members}) => <li key={source.id}>
          <span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}</span>
          <SourceChannels source={source} />
          {members.some(member => member.is_active) && <small>Aktywne źródło / kanał</small>}
        </li>)}</ul>
        {limits[key] < groups[key].length && <Button onClick={() => setLimits(previous => ({...previous, [key]: previous[key] + 30}))}>Pokaż więcej<span className="sr-only">: {label}</span></Button>}
        {!groups[key].length && config.isSuccess && <p>Brak źródeł dla wybranych filtrów.</p>}
      </section>)}
    </div>
    <section className="sc-source-page__progress"><p>POSTĘP KATALOGU</p><h2>Jak rozwija się baza źródeł?</h2><ArchiveProgress /></section>

  </InfoPage>;
}
