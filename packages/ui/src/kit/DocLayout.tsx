import { InfoPage, type InfoPageProps } from "./InfoPage";

export type DocSection = { id: string; label: string };
export type DocLayoutProps = Omit<InfoPageProps, "longTitle"> & {
  sections: readonly DocSection[];
  version: string;
  updatedAt: string;
};

/** Dokument 68ch ze spisem 200px; na telefonie spis rozwija się bez JavaScriptu. */
export function DocLayout({ sections, ...props }: DocLayoutProps) {
  const links = <ol>{sections.map(section => <li key={section.id}>
    <a href={`#${section.id}`}>{section.label}</a>
  </li>)}</ol>;
  return <div className="sc-doc-layout">
    <aside className="sc-doc-layout__aside">
      <nav className="sc-doc-layout__toc" aria-label="Na tej stronie">
        <div className="sc-doc-layout__desktop"><p>Na tej stronie</p>{links}</div>
        <details className="sc-doc-layout__mobile"><summary>Na tej stronie</summary>{links}</details>
      </nav>
    </aside>
    <InfoPage {...props} />
  </div>;
}
