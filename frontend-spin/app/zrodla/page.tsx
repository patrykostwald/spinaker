"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortalConfig } from '@spin-clinic/ui';
import type { Source } from '@spin-clinic/ui';
import { ArchiveProgress } from '@spin-clinic/ui';
import { Button, InfoPage, SearchField } from '@spin-clinic/ui/kit';

const IMPORTANT = /onet|wp|wirtualna polska|tvn|polsat|rmf|radio zet|gazeta\.pl|interia|reuters|pap|rzeczpospolita/i;

function sourceGroups(sources: Source[]) {
  return {
    important: sources.filter(source => IMPORTANT.test(source.name)),
    public: sources.filter(source => source.source_type === 'institution'),
    media: sources.filter(source => !IMPORTANT.test(source.name) && source.source_type !== 'institution'),
  };
}

/** Znaczki przy źródle: co już mamy (zgoda / dane publiczne, YouTube, X), a na co czekamy. */
function SourceChannels({ source }: { source: Source }) {
  const channelOnly = (source.url || '').includes('youtube.com');
  const youtube = channelOnly ? source.url : source.youtube_url;
  return <small className="sc-source-chips">
    {channelOnly ? null : source.access === 'approved'
      ? <span className="sc-source-chip is-on" title="Zgoda wydawcy albo dane publiczne na jawnych zasadach">Zgoda</span>
      : <span className="sc-source-chip" title="Czekamy na zgodę wydawcy">weryfikacja</span>}
    {youtube ? <a className="sc-source-chip is-on" href={youtube} target="_blank" rel="noopener noreferrer" aria-label={`${source.name} na YouTube`}>YouTube</a> : null}
    {source.x_handle ? <a className="sc-source-chip is-on" href={`https://x.com/${source.x_handle}`} target="_blank" rel="noopener noreferrer" aria-label={`${source.name} na X (@${source.x_handle})`}>X</a> : null}
  </small>;
}

export default function SourcesPage() {
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig });
  const [search, setSearch] = useState('');
  const [suggestion, setSuggestion] = useState('');
  // Kanał YouTube serwisu, który już jest w katalogu, pokazujemy znaczkiem przy serwisie — nie jako osobne źródło.
  const visible = useMemo(() => {
    const all = config.data?.sources ?? [];
    const linkedChannels = new Set(all.map(source => source.youtube_url).filter(Boolean));
    return all.filter(source => !linkedChannels.has(source.url) && source.name.toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl')));
  }, [config.data?.sources, search]);
  const groups = sourceGroups(visible);
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
      <div><dt>W katalogu</dt><dd>{stats?.catalog_total ?? '—'}</dd></div>
      <div><dt>Aktywne</dt><dd>{stats?.active ?? '—'}</dd></div>
      <div><dt>Oczekuje na odpowiedź</dt><dd>{stats?.awaiting_response ?? '—'}</dd></div>
    </dl>
    <SearchField className="sc-source-page__search" label="Znajdź źródło" value={search} onChange={setSearch} placeholder="Nazwa źródła" />
    <ul className="sc-source-legend" aria-label="Oznaczenia">
      <li><span className="sc-source-chip is-on">Zgoda</span> zgoda wydawcy albo dane publiczne na jawnych zasadach</li>
      <li><span className="sc-source-chip is-on">YouTube</span> <span className="sc-source-chip is-on">X</span> oficjalny kanał i konto, podlinkowane na stronie źródła</li>
      <li><span className="sc-source-chip">weryfikacja</span> czekamy na zgodę albo potwierdzenie kanału</li>
    </ul>
    <div className="sc-source-page__grid">
      {([['important', 'Największe media'], ['media', 'Media'], ['public', 'Publiczne']] as const).map(([key, label]) => <section key={key}>
        <h2>{label}<span>{groups[key].length}</span></h2>
        <ul>{groups[key].map(source => <li key={source.id}><span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}</span>
          <SourceChannels source={source} /></li>)}</ul>
      </section>)}
    </div>
    <section className="sc-source-page__progress"><p>POSTĘP KATALOGU</p><h2>Jak rozwija się baza źródeł?</h2><ArchiveProgress /></section>
    <section className="sc-source-page__suggestion"><p>ROZBUDOWA BAZY</p><h2>Zaproponuj źródło</h2><p>Podaj adres strony, którą warto sprawdzić. Każde źródło weryfikujemy przed uruchomieniem.</p>
      <form className="sc-search-form" onSubmit={suggest}><SearchField label="Adres proponowanego źródła" value={suggestion} onChange={setSuggestion} placeholder="https://…" inputType="url" required /><Button type="submit" variant="primary" disabled={!contact}>Wyślij sugestię</Button></form>
      {!contact && <small>Formularz połączymy ze skrzynką kontaktową po wskazaniu adresu kontaktowego.</small>}
    </section>
  </InfoPage>;
}
