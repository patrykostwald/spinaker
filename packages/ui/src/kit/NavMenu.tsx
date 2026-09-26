"use client";

/**
 * NavMenu — przezroczysta, przyklejona szapka (docs/UI_KIT_PLAN.md → «Компоненты» NavMenu,
 * «Оживление каждого элемента → Меню и шапка»).
 *
 * Dolna kreska pojawia się DOPIERO po przewinięciu — wykrywana 1px sentinelem przez
 * IntersectionObserver, nigdy przez nasłuch scrolla. Aktywny punkt dostaje aria-current="page"
 * ORAZ wspólny MorphIndicator (layoutId), który przejeżdża między punktami na sprężynie `move`.
 * Poniżej 768px lista chowa się w panel rozwijany przyciskiem z ikoną MenuClose.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { Button } from "./Button";
import { Dropdown, type DropdownItem } from "./Dropdown";
import { MenuClose } from "./icons/MenuClose";
import { MorphIndicator } from "./motion/MorphIndicator";
import { useDismissable } from "./useDismissable";
import { useMotionTokens } from "./motion/useMotionTokens";
import { RADIUS } from "./tokens";

export type NavItem = {
  label: string;
  href: string;
  current?: boolean;
  items?: NavItem[];
};

export type NavMenuProps = {
  items: NavItem[];
  /** Domyślnie 'Nawigacja główna'. */
  ariaLabel?: string;
  /** Slot na wezwanie do działania po prawej (np. Zaloguj). */
  cta?: ReactNode;
  /** Domyślnie true — `position: sticky` u góry. */
  sticky?: boolean;
  /** Etykieta dropdownu z punktami, które nie zmieściły się w rzędzie. Domyślnie 'Więcej'. */
  overflowLabel?: string;
  /** Slot na wordmark. */
  brand?: ReactNode;
  /** Slot na pole wyszukiwania (np. SearchField). Ukrywany poniżej 768px — brak miejsca w rzędzie. */
  search?: ReactNode;
  /**
   * `centered`: pole szukania na środku rzędu, po lewej wordmark + punkty (prowadzą do pola),
   * po prawej cta. Domyślnie `inline` — dotychczasowy rząd od lewej.
   */
  layout?: "inline" | "centered";
};

const MotionLink = motion(Link);
const INDICATOR_ID = "sc-navmenu-indicator";
const MOBILE_CASCADE_STEP = 0.03;
const MOBILE_CASCADE_CAP = 9;

/**
 * Ile punktów mieści się w rzędzie, zanim reszta trafi do dropdownu `overflowLabel`.
 * Stała, nie pomiar szerokości: ResizeObserver policzony na piksele byłby tu spekulacją
 * ponad to, co specyfikacja opisuje („Компоненты” wymienia tylko sam prop overflowLabel).
 */
const MAX_VISIBLE_ITEMS = 5;

function NavLink({ item }: { item: NavItem }) {
  const m = useMotionTokens();
  return (
    <MotionLink
      href={item.href}
      className="sc-navmenu__link sc-hoverable"
      aria-current={item.current ? "page" : undefined}
      whileTap={{ scale: m.scale(0.97), transition: m.t("press") }}
    >
      {item.label}
      <MorphIndicator id={INDICATOR_ID} active={Boolean(item.current)} />
    </MotionLink>
  );
}

export function NavMenu({
  items,
  ariaLabel = "Nawigacja główna",
  cta,
  sticky = true,
  overflowLabel = "Więcej",
  brand,
  search,
  layout = "inline",
}: NavMenuProps) {
  const m = useMotionTokens();
  const router = useRouter();
  const instanceId = useId();
  const mobilePanelId = `sc-navmenu-mobile-${instanceId}`;
  // R0 «один живой элемент»: панель вырастает из кнопки меню — общий layoutId с «семенем» в кнопке,
  // ровно один держатель за раз (семя, пока закрыто; панель, пока открыто). Как в Dropdown.
  const seedId = `${instanceId}-menu-surface`;
  const toggleRef = useRef<HTMLButtonElement | HTMLAnchorElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Kromka u dołu szapki pojawia się dopiero po przewinięciu — sentinel 1px zamiast nasłuchu scrolla.
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting), { threshold: 0 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const dismissRef = useDismissable<HTMLDivElement>({
    open: mobileOpen,
    onClose: () => setMobileOpen(false),
    triggerRef: toggleRef as RefObject<HTMLElement>,
  });

  const visible = items.slice(0, MAX_VISIBLE_ITEMS);
  const overflow = items.slice(MAX_VISIBLE_ITEMS);
  const overflowItems: DropdownItem[] = overflow.map((item) => ({ value: item.href, label: item.label }));
  const overflowActive = overflow.some((item) => item.current);

  function goTo(item: DropdownItem) {
    router.push(item.value);
  }

  return (
    <>
      <div ref={sentinelRef} className="sc-navmenu__sentinel" aria-hidden="true" />
      <nav
        className="sc-navmenu sc-chrome"
        aria-label={ariaLabel}
        data-sticky={sticky || undefined}
        data-stuck={stuck || undefined}
        data-layout={layout}
      >
        <div className="sc-navmenu__row">
          {/* start/end mają `display: contents` w układzie `inline` — rząd wygląda jak dotąd. */}
          <div className="sc-navmenu__start">
          {brand && <div className="sc-navmenu__brand">{brand}</div>}

          <ul className="sc-navmenu__list" role="list">
            {visible.map((item) => (
              <li key={item.href} className="sc-navmenu__item">
                {item.items?.length ? (
                  <span className="sc-navmenu__item-wrap">
                    <Dropdown
                      label={item.label}
                      ariaLabel={item.label}
                      mode="menu"
                      triggerVariant="ghost"
                      items={item.items.map((sub) => ({ value: sub.href, label: sub.label }))}
                      onSelect={goTo}
                    />
                    <MorphIndicator id={INDICATOR_ID} active={Boolean(item.current)} />
                  </span>
                ) : (
                  <NavLink item={item} />
                )}
              </li>
            ))}
            {overflowItems.length > 0 && (
              <li className="sc-navmenu__item">
                <span className="sc-navmenu__item-wrap">
                  <Dropdown
                    label={overflowLabel}
                    ariaLabel={overflowLabel}
                    mode="menu"
                    triggerVariant="ghost"
                    items={overflowItems}
                    onSelect={goTo}
                  />
                  <MorphIndicator id={INDICATOR_ID} active={overflowActive} />
                </span>
              </li>
            )}
          </ul>
          </div>

          {search && <div className="sc-navmenu__search">{search}</div>}

          <div className="sc-navmenu__end">
          {cta && <div className="sc-navmenu__cta">{cta}</div>}

          <span className="sc-navmenu__toggle-wrap">
            {m.morph && !mobileOpen && (
              <motion.span aria-hidden="true" className="sc-navmenu__toggle-seed" layoutId={seedId} style={{ borderRadius: RADIUS.md }} />
            )}
            <Button
              ref={toggleRef}
              shape="icon"
              variant="ghost"
              size="md"
              className="sc-navmenu__toggle"
              aria-label={mobileOpen ? "Zamknij menu" : "Otwórz menu"}
              aria-expanded={mobileOpen}
              aria-controls={mobilePanelId}
              iconStart={<MenuClose open={mobileOpen} />}
              onClick={() => setMobileOpen((value) => !value)}
            />
          </span>
          </div>
        </div>

        <div id={mobilePanelId} ref={dismissRef} className="sc-navmenu__mobile-wrap">
          <AnimatePresence>
          {mobileOpen && (
          <motion.div
            className="sc-navmenu__mobile"
            layoutId={m.morph ? seedId : undefined}
            style={{ borderRadius: RADIUS.xl }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={m.t(mobileOpen ? "ui" : "collapse")}
          >
            {cta && <div className="sc-navmenu__mobile-cta">{cta}</div>}
            <ul className="sc-navmenu__mobile-list" role="list">
              {items.map((item, index) => (
                <li key={item.href}>
                  <motion.div
                    initial={{ opacity: 0, y: m.rise }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={m.t("ui", { delay: Math.min(index, MOBILE_CASCADE_CAP) * MOBILE_CASCADE_STEP })}
                  >
                    <Link
                      href={item.href}
                      className="sc-navmenu__mobile-link"
                      aria-current={item.current ? "page" : undefined}
                      onClick={() => setMobileOpen(false)}
                    >
                      {item.label}
                    </Link>
                    {item.items?.length ? (
                      <ul className="sc-navmenu__mobile-sublist" role="list">
                        {item.items.map((sub) => (
                          <li key={sub.href}>
                            <Link
                              href={sub.href}
                              className="sc-navmenu__mobile-link sc-navmenu__mobile-link--sub"
                              aria-current={sub.current ? "page" : undefined}
                              onClick={() => setMobileOpen(false)}
                            >
                              {sub.label}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </motion.div>
                </li>
              ))}
            </ul>
          </motion.div>
          )}
          </AnimatePresence>
        </div>
      </nav>
    </>
  );
}

/* ---------------------------------------------------------------------- */

export type NavCategory = {
  label: string;
  href: string;
  current?: boolean;
};

export type NavCategoriesProps = {
  items: NavCategory[];
  /** Domyślnie 'Kategorie'. */
  ariaLabel?: string;
};

/**
 * Pasek kategorii (jak NEWS/SPORTS/LIFE w referencji): pozioma lista linków ze wspólnym
 * przejeżdżającym wskaźnikiem, przewijana poziomo na telefonie.
 */
export function NavCategories({ items, ariaLabel = "Kategorie" }: NavCategoriesProps) {
  const m = useMotionTokens();
  return (
    <nav className="sc-nav-categories" aria-label={ariaLabel}>
      <ul className="sc-nav-categories__list" role="list">
        {items.map((item) => (
          <li key={item.href} className="sc-nav-categories__item">
            <MotionLink
              href={item.href}
              className="sc-nav-categories__link sc-hoverable"
              aria-current={item.current ? "page" : undefined}
              whileTap={{ scale: m.scale(0.97), transition: m.t("press") }}
            >
              {item.label}
              <MorphIndicator id="sc-nav-categories-indicator" active={Boolean(item.current)} />
            </MotionLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
