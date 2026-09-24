"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortalConfig } from '@spin-clinic/ui';
import type { Source } from '@spin-clinic/ui';
import { ArchiveProgress } from '@spin-clinic/ui';
import { Button, SearchField } from '@spin-clinic/ui/kit';

const IMPORTANT = /onet|wp|wirtualna polska|tvn|polsat|rmf|radio zet|gazeta\.pl|interia|reuters|pap|rzeczpospolita/i;

function sourceGroups(sources: Source[]) {
  return {
    important: sources.filter(source => IMPORTANT.test(source.name)),
    public: sources.filter(source => source.source_type === 'institution'),
    media: sources.filter(source => !IMPORTANT.test(source.name) && source.source_type !== 'institution'),
  };
}

export default function SourcesPage() {
  const config = useQuery({ queryKey: ['mvp-portal-config'], queryFn: getPortalConfig });
  const [search, setSearch] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const visible = useMemo(() => (config.data?.sources ?? []).filter(source => source.name.toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'))), [config.data?.sources, search]);
  const groups = sourceGroups(visible);
  const contact = process.env.NEXT_PUBLIC_CONTACT_EMAIL;
  const stats = config.data?.source_stats;

  function suggest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!contact || !suggestion.trim()) return;
    window.location.href = `mailto:${contact}?subject=${encodeURIComponent('Sugestia źródła dla spin.clinic')}&body=${encodeURIComponent(`Proponowane źródło: ${suggestion.trim()}`)}`;
  }

  return <article className="sc-source-page">
    <header className="sc-source-page__hero"><p>KATALOG</p><h1>Źródła</h1><p>Pokazujemy źródła aktywne oraz kandydatury, które czekają na weryfikację kanału i zasad wykorzystania.</p></header>
    <dl className="sc-source-page__stats">
      <div><dt>W katalogu</dt><dd>{stats?.catalog_total ?? '—'}</dd></div>
      <div><dt>Aktywne</dt><dd>{stats?.active ?? '—'}</dd></div>
      <div><dt>Oczekuje na odpowiedź</dt><dd>{stats?.awaiting_response ?? '—'}</dd></div>
    </dl>
    <SearchField className="sc-source-page__search" label="Znajdź źródło" value={search} onChange={setSearch} placeholder="Nazwa źródła" />
    <div className="sc-source-page__grid">
      {([['important', 'Największe media'], ['media', 'Media'], ['public', 'Publiczne']] as const).map(([key, label]) => <section key={key}>
        <h2>{label}<span>{groups[key].length}</span></h2>
        <ul>{groups[key].map(source => <li key={source.id}><span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}</span><small className={source.is_active ? 'is-active' : ''}>{source.is_active ? 'Aktywne' : 'Katalog · weryfikacja'}</small></li>)}</ul>
      </section>)}
    </div>
    <section className="sc-source-page__progress"><p>POSTĘP KATALOGU</p><h2>Jak rozwija się baza źródeł?</h2><ArchiveProgress /></section>
    <section className="sc-source-page__suggestion"><p>ROZBUDOWA BAZY</p><h2>Zaproponuj źródło</h2><p>Podaj adres strony, którą warto sprawdzić. Każde źródło weryfikujemy przed uruchomieniem.</p>
      <form className="sc-search-form" onSubmit={suggest}><SearchField label="Adres proponowanego źródła" value={suggestion} onChange={setSuggestion} placeholder="https://…" inputType="url" required /><Button type="submit" variant="primary" disabled={!contact}>Wyślij sugestię</Button></form>
      {!contact && <small>Formularz połączymy ze skrzynką redakcyjną po wskazaniu adresu kontaktowego.</small>}
    </section>
  </article>;
}
