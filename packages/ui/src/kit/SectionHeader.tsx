import type { ReactNode } from "react";

export type SectionHeaderProps = {
  variant?: "page" | "section" | "panel";
  title: ReactNode;
  titleId?: string;
  kicker?: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  action?: ReactNode;
  link?: ReactNode;
  longTitle?: boolean;
};

/** Wspólna hierarchia nagłówków; akcje zawijają się pod tekstem. */
export function SectionHeader({ variant = "section", title, titleId, kicker, subtitle, meta, action, link, longTitle }: SectionHeaderProps) {
  const Heading = variant === "page" ? "h1" : variant === "section" ? "h2" : "h3";
  return <header className="sc-section-header" data-variant={variant} data-long-title={longTitle || undefined}>
    <div className="sc-section-header__copy">
      {kicker && <div className="sc-section-header__kicker">{kicker}</div>}
      <Heading id={titleId} className="sc-section-header__title">{title}</Heading>
      {meta && <div className="sc-section-header__meta">{meta}</div>}
      {subtitle && <div className="sc-section-header__subtitle">{subtitle}</div>}
    </div>
    {(action || link) && <div className="sc-section-header__actions">{action}{link}</div>}
  </header>;
}
