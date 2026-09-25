"use client";

/**
 * SiteFooter (docs/UI_KIT_PLAN.md → «Компоненты» SiteFooter, «Оживление каждого элемента → Футер»).
 * Każda kolumna to WŁASNY `<nav aria-label>` z prawdziwym `<ul>` — obecny footer w
 * `PortalHome.tsx` ma jeden nieoznaczony `<nav>` z gołymi `<a>`, tego tu nie powielamy.
 * Siatka reaguje na WŁASNĄ szerokość (container queries), nie szerokość okna — działa też
 * wewnątrz wąskiej ramki witryny.
 *
 * `sticky`: jeden wiersz przyklejony do dołu okna — wordmark, kolumny linków (np. źródła, informacje)
 * i przycisk wsparcia na jednej linii. `note` i `bottom` renderują się tylko w układzie zwykłym.
 */

import type { ReactNode } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "./Button";
import { useMotionTokens } from "./motion/useMotionTokens";

export type SiteFooterColumn = {
  title: string;
  links: { label: string; href: string }[];
};

export type SiteFooterCta = {
  eyebrow?: string;
  label: string;
  href: string;
};

export type SiteFooterProps = {
  /** Slot na wordmark. */
  brand: ReactNode;
  /** Tekst redakcyjny (dosłowny dysklaimer) — nie skracamy ani nie parafrazujemy. */
  note?: ReactNode;
  columns: SiteFooterColumn[];
  cta?: SiteFooterCta;
  /** Dolny wiersz — np. data wersji, prawa. */
  bottom?: ReactNode;
  /** Jednowierszowa stopka zawsze widoczna u dołu okna (patrz opis modułu). */
  sticky?: boolean;
};

const MotionLink = motion(Link);
const COLUMN_CASCADE_STEP = 0.04;
const COLUMN_CASCADE_CAP = 9;

function FooterLink({ href, children }: { href: string; children: ReactNode }) {
  const m = useMotionTokens();
  return (
    <MotionLink
      href={href}
      className="sc-footer__link sc-hoverable"
    >
      {children}
    </MotionLink>
  );
}

export function SiteFooter({ brand, note, columns, cta, bottom, sticky = false }: SiteFooterProps) {
  const m = useMotionTokens();
  const columnsRow = (
    <div className="sc-footer__columns">
      {columns.map((column, index) => (
        <motion.nav
          key={column.title}
          aria-label={column.title}
          className="sc-footer__column"
          initial={{ opacity: 0, y: m.rise }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={m.t("ui", { delay: Math.min(index, COLUMN_CASCADE_CAP) * COLUMN_CASCADE_STEP })}
        >
          <p className="sc-footer__column-title sc-t-caption sc-text-3">{column.title}</p>
          <ul className="sc-footer__list" role="list">
            {column.links.map((link) => (
              <li key={link.href}>
                <FooterLink href={link.href}>{link.label}</FooterLink>
              </li>
            ))}
          </ul>
        </motion.nav>
      ))}
    </div>
  );

  if (sticky) {
    return (
      <footer role="contentinfo" className="sc-footer" data-sticky>
        <div className="sc-footer__bar">
          <div className="sc-footer__brand">{brand}</div>
          {columnsRow}
          {cta ? (
            <Button href={cta.href} variant="primary" size="sm" className="sc-footer__bar-cta">
              {cta.label}
            </Button>
          ) : null}
        </div>
      </footer>
    );
  }

  return (
    <footer role="contentinfo" className="sc-footer">
      <div className="sc-footer__top">
        <div className="sc-footer__intro">
          <div className="sc-footer__brand">{brand}</div>
          {note && <p className="sc-footer__note sc-t-body-s sc-text-2">{note}</p>}
        </div>

        {cta && (
          <div className="sc-footer__cta">
            {cta.eyebrow && <p className="sc-t-caption sc-text-3">{cta.eyebrow}</p>}
            <Button href={cta.href} variant="primary" size="md">
              {cta.label}
            </Button>
          </div>
        )}
      </div>

      {columnsRow}

      {bottom && <div className="sc-footer__bottom sc-t-caption sc-text-3">{bottom}</div>}
    </footer>
  );
}
