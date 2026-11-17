import type { ReactNode } from "react";

/**
 * Nagłówek strony v3 (reguła dociągania): lewa kolumna - kicker przy górnej krawędzi, blok tytuł + opis + akcje
 * dociągnięty do dołu; prawa kolumna (opcjonalna) dociągnięta do dołu, wspólna dolna krawędź z akcjami.
 */
export function PageHeaderV3({ nav, kicker, title, sub, actions, aside, titleId }: {
  /** podnawigacja sekcji (np. ClinicNav) - część nagłówka, nad tytułem */
  nav?: ReactNode; kicker?: ReactNode; title: ReactNode; sub?: ReactNode; actions?: ReactNode; aside?: ReactNode; titleId?: string;
}) {
  return <header className="sc-v3-hh sc-v3-ph" data-aside={aside ? "" : undefined}>
    {nav ? <div className="sc-v3-ph__nav">{nav}</div> : null}
    <div className="sc-v3-hh__main">
      {kicker ? <p className="sc-v3-hh__k">{kicker}</p> : null}
      <div className="sc-v3-hh__block">
        <h1 id={titleId}>{title}</h1>
        {sub ? <p className="sc-v3-hh__sub">{sub}</p> : null}
        {actions ? <div className="sc-v3-hh__act">{actions}</div> : null}
      </div>
    </div>
    {aside ? <div className="sc-v3-hh__stats">{aside}</div> : null}
  </header>;
}
