"use client";

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortalConfig } from '@spin-clinic/ui';
import type { Source } from '@spin-clinic/ui';
import { ArchiveProgress } from '@spin-clinic/ui';

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

  return <article className="mvp-info-page mvp-sources-page">
    <header className="mvp-info-hero"><p>KATALOG</p><h1>Źródła</h1><p>Pokazujemy źródła aktywne oraz kandydatury, które czekają na weryfikację kanału i zasad wykorzystania.</p></header>
    <dl className="mvp-source-stats">
      <div><dt>W katalogu</dt><dd>{stats?.catalog_total ?? '—'}</dd></div>
      <div><dt>Aktywne</dt><dd>{stats?.active ?? '—'}</dd></div>
      <div><dt>Oczekuje na odpowiedź</dt><dd>{stats?.awaiting_response ?? '—'}</dd></div>
    </dl>
    <label className="mvp-source-directory-search">Znajdź źródło<input value={search} onChange={event => setSearch(event.target.value)} type="search" placeholder="Nazwa źródła" /></label>
    <div className="mvp-source-directory-grid">
      {([['important', 'Największe media'], ['media', 'Media'], ['public', 'Publiczne']] as const).map(([key, label]) => <section key={key}>
        <h2>{label}<span>{groups[key].length}</span></h2>
        <ul>{groups[key].map(source => <li key={source.id}><span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}</span><small className={source.is_active ? 'is-active' : ''}>{source.is_active ? 'Aktywne' : 'Katalog · weryfikacja'}</small></li>)}</ul>
      </section>)}
    </div>
    <section className="mvp-source-progress"><p>POSTĘP KATALOGU</p><h2>Jak rozwija się baza źródeł?</h2><ArchiveProgress /></section>
    <section className="mvp-source-suggestion"><p>ROZBUDOWA BAZY</p><h2>Zaproponuj źródło</h2><p>Podaj adres strony, którą warto sprawdzić. Każde źródło weryfikujemy przed uruchomieniem.</p>
      <form onSubmit={suggest}><input type="url" value={suggestion} onChange={event => setSuggestion(event.target.value)} placeholder="https://…" required /><button type="submit" disabled={!contact}>Wyślij sugestię</button></form>
      {!contact && <small>Formularz połączymy ze skrzynką redakcyjną po wskazaniu adresu kontaktowego.</small>}
    </section>
  </article>;
}
