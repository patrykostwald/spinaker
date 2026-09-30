import type { ReactNode } from "react";
import { SectionHeader } from "./SectionHeader";

export type InfoPageProps = {
  eyebrow: string;
  title: string;
  lead: ReactNode;
  children: ReactNode;
  className?: string;
  longTitle?: boolean;
  version?: string;
  updatedAt?: string;
  actions?: ReactNode;
};

/** Wspólny, czytelny układ dla stron zasad, prywatności, dostępu i wsparcia. */
export function InfoPage({ eyebrow, title, lead, children, className, longTitle, version, updatedAt, actions }: InfoPageProps) {
  const meta = version || updatedAt ? <>
    {version && `Wersja ${version}`}{version && updatedAt && " · "}
    {updatedAt && <time dateTime={updatedAt}>{new Date(`${updatedAt}T12:00:00Z`).toLocaleDateString("pl-PL", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Warsaw" })}</time>}
  </> : undefined;
  return (
    <article className={["sc-info-page", className].filter(Boolean).join(" ")}>
      <div className="sc-info-page__hero">
        <SectionHeader variant="page" kicker={eyebrow} title={title} longTitle={longTitle} meta={meta} subtitle={lead} />
        {actions && <div className="sc-info-page__actions">{actions}</div>}
      </div>
      <div className="sc-info-page__body">{children}</div>
    </article>
  );
}
