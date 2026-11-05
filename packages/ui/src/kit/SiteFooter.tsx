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
  actions?: ReactNode;
  /** Stałe linki w pasku sticky (komputer): np. Metodologia, Karta, Źródła — bez otwierania „Więcej”. */
  quickLinks?: { label: string; href: string; current?: boolean }[];
  quickLinksLabel?: string;
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

export function SiteFooter({ brand, note, columns, cta, bottom, sticky = false, above, actions, quickLinks, quickLinksLabel = "Zaufanie i źródła" }: SiteFooterProps) {
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
          {quickLinks?.length ? (
            <nav className="sc-footer__quick" aria-label={quickLinksLabel}>
              {quickLinks.map(link => <Link key={link.href} href={link.href} className="sc-footer__quick-link" aria-current={link.current ? "page" : undefined}>{link.label}</Link>)}
            </nav>
          ) : null}
          {actions}
          <details className="sc-footer__more" onToggle={event => event.currentTarget.querySelector("summary")?.setAttribute("aria-expanded", String(event.currentTarget.open))} onKeyDown={event => {
            if (event.key === "Escape") {
              event.currentTarget.open = false;
              event.currentTarget.querySelector("summary")?.focus();
            }
          }}>
            <summary aria-expanded="false">Więcej<svg className="sc-footer__more-chevron" aria-hidden="true" focusable="false" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 10l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></summary>
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
      <div className="sc-footer-dock" ref={dockRef} data-idle="true">
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
      {actions}

      {bottom && <div className="sc-footer__bottom sc-t-caption sc-text-3">{bottom}</div>}
    </footer>
  );
}


/** Dok jest „uśpiony” (poza ekranem), dopóki czytelnik nie przewinie ~90% wysokości okna ani nie dotrze do końca strony. */
function setIdle(node: HTMLElement, y: number, nearBottom: boolean) {
  if (y > window.innerHeight * 0.9 || nearBottom || node.contains(document.activeElement) || node.querySelector("details[open]")) delete node.dataset.idle;
  else node.dataset.idle = "true";
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
          setIdle(node, y, nearBottom);
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
      if (node.contains(target)) { delete node.dataset.hidden; delete node.dataset.idle; }
      else {
        node.querySelectorAll("details[open]").forEach(menu => menu.removeAttribute("open"));
        const rect = target.getBoundingClientRect();
        const bottom = window.innerHeight - node.getBoundingClientRect().height - 12;
        if (rect.bottom > bottom && rect.top < window.innerHeight) window.scrollBy({ top: rect.bottom - bottom, behavior: "instant" });
      }
    };
    // Pasek wsparcia nie wyskakuje od pierwszej sekundy: pojawia się po przewinięciu ok. jednego ekranu (F12).
    if (ref.current) setIdle(ref.current, window.scrollY, window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 80);
    // Wysokość strony zmienia się po wczytaniu danych i po zmianie trasy: wtedy krótka strona nie może zostać z ukrytym dokiem.
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (ref.current) setIdle(ref.current, window.scrollY, window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 80);
    });
    resize?.observe(document.documentElement);
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("focusin", onFocus);
    return () => {
      resize?.disconnect();
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("focusin", onFocus);
    };
  }, []);
  return ref;
}
