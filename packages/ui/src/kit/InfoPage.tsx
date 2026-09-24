import type { ReactNode } from "react";

export type InfoPageProps = {
  eyebrow: string;
  title: string;
  lead: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Wspólny, czytelny układ dla stron zasad, prywatności, dostępu i wsparcia. */
export function InfoPage({ eyebrow, title, lead, children, className }: InfoPageProps) {
  return (
    <article className={["sc-info-page", className].filter(Boolean).join(" ")}>
      <header className="sc-info-page__hero">
        <p className="sc-t-meta sc-info-page__eyebrow">{eyebrow}</p>
        <h1 className="sc-t-display sc-info-page__title">{title}</h1>
        <div className="sc-t-body sc-text-2 sc-info-page__lead">{lead}</div>
      </header>
      <div className="sc-info-page__body">{children}</div>
    </article>
  );
}
