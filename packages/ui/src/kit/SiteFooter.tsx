"use client";

import { useEffect, useRef } from "react";

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
  /** Wiersz nad paskiem stopki `sticky` (np. pasek wsparcia z licznikiem). */
  above?: ReactNode;
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

export function SiteFooter({ brand, note, columns, cta, bottom, sticky = false, above }: SiteFooterProps) {
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

  // Przewijanie w dół chowa przyklejony dół (pasek wsparcia + stopka), w górę — pokazuje (audyt UX 28.09).
  const dockRef = useHideOnScroll();
  if (sticky) {
    const bar = (
      <footer role="contentinfo" className="sc-footer" data-sticky>
        <div className="sc-footer__bar">
          <div className="sc-footer__brand">{brand}</div>
          <details className="sc-footer__more" onKeyDown={event => {
            if (event.key === "Escape") {
              event.currentTarget.open = false;
              event.currentTarget.querySelector("summary")?.focus();
            }
          }}>
            <summary>Więcej</summary>
            <div className="sc-footer__menu" onClick={event => {
              if ((event.target as HTMLElement).closest("a")) event.currentTarget.closest("details")?.removeAttribute("open");
            }}>
              {columnsRow}
              {above && <div className="sc-footer__support">{above}</div>}
            </div>
          </details>
          {cta ? (
            <Button href={cta.href} variant="primary" size="sm" className="sc-footer__bar-cta">
              {cta.label}
            </Button>
          ) : null}
        </div>
      </footer>
    );
    // Jeden dok także bez komunikatu wsparcia; linki i komunikat mieszczą się w menu.
    return (
      <div className="sc-footer-dock" ref={dockRef}>
        {bar}
      </div>
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


function useHideOnScroll() {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let last = window.scrollY;
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(() => {
        const y = window.scrollY;
        const node = ref.current;
        if (node) {
          const nearBottom = window.innerHeight + y >= document.documentElement.scrollHeight - 80;
          if (y > last + 6 && y > 120 && !nearBottom && !node.contains(document.activeElement) && !node.querySelector("details[open]")) node.dataset.hidden = "true";
          else if (y < last - 6 || nearBottom || y <= 120) delete node.dataset.hidden;
        }
        if (Math.abs(y - last) > 6) last = y;
        ticking = false;
      });
    };
    const onFocus = (event: FocusEvent) => {
      const node = ref.current;
      const target = event.target;
      if (!node || !(target instanceof HTMLElement)) return;
      if (node.contains(target)) delete node.dataset.hidden;
      else {
        node.querySelectorAll("details[open]").forEach(menu => menu.removeAttribute("open"));
        const rect = target.getBoundingClientRect();
        const bottom = window.innerHeight - node.getBoundingClientRect().height - 12;
        if (rect.bottom > bottom && rect.top < window.innerHeight) window.scrollBy({ top: rect.bottom - bottom, behavior: "instant" });
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("focusin", onFocus);
    return () => {
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("focusin", onFocus);
    };
  }, []);
  return ref;
}
