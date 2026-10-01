import { InfoPage, type InfoPageProps } from "./InfoPage";

export type DocSection = { id: string; label: string };
export type DocLayoutProps = Omit<InfoPageProps, "longTitle"> & {
  sections: readonly DocSection[];
  version: string;
  updatedAt: string;
  alternateHref?: string;
};

/** Dokument 68ch ze spisem 200px; na telefonie spis rozwija się bez JavaScriptu. */
export function DocLayout({ sections, alternateHref, lang = "pl", actions, ...props }: DocLayoutProps) {
  const onThisPage = lang === "en" ? "On this page" : "Na tej stronie";
  const languageSwitch = alternateHref ? <nav className="sc-doc-language" aria-label={lang === "en" ? "Document language" : "Język dokumentu"}>
    {lang === "pl" ? <span lang="pl" aria-current="page">PL</span> : <a lang="pl" hrefLang="pl" href={alternateHref}>PL</a>}
    <span aria-hidden="true"> · </span>
    {lang === "en" ? <span lang="en" aria-current="page">EN</span> : <a lang="en" hrefLang="en" href={alternateHref}>EN</a>}
  </nav> : null;
  const links = <ol>{sections.map(section => <li key={section.id}>
    <a href={`#${section.id}`}>{section.label}</a>
  </li>)}</ol>;
  return <div className="sc-doc-layout" lang={lang}>
    <aside className="sc-doc-layout__aside">
      <nav className="sc-doc-layout__toc" aria-label={onThisPage}>
        <div className="sc-doc-layout__desktop"><p>{onThisPage}</p>{links}</div>
        <details className="sc-doc-layout__mobile"><summary>{onThisPage}</summary>{links}</details>
      </nav>
    </aside>
    <InfoPage {...props} lang={lang} actions={languageSwitch || actions ? <>{languageSwitch}{actions}</> : undefined} />
  </div>;
}
