"use client";
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useFeature } from '../../lib/features';
import { clinicNavigation, isClinicNavigationCurrent } from '../../lib/siteNavigation';

type Item = { label: string; href: string; current: boolean; accent?: boolean };

export const FEED_SOURCES = [
  { value: 'all', label: 'Wszystkie' }, { value: 'drspin', label: 'Dr. Spin' }, { value: 'readers', label: 'Czytelnicy' }, { value: 'izba', label: 'Izba przyjęć' },
] as const;
export const FEED_SORTS = [
  { value: 'hot', label: 'Najgorętsze' }, { value: 'new', label: 'Najnowsze' }, { value: 'best', label: 'Najlepiej oceniane' }, { value: 'comments', label: 'Komentowane' },
] as const;

const ABOUT = [['spin', 'Czym jest spin'], ['projekt', 'Projekt'], ['operator', 'Operator'], ['finansowanie', 'Finansowanie'], ['obserwuj', 'Obserwuj'], ['kontakt', 'Kontakt']] as const;

/**
 * Pasek kategorii nad treścią (właściciel 3.10, szkic w Figmie): pozycje rozłożone na całą szerokość
 * i zależne od działu w lewym pasku - Tropy: źródła i kolejność, Klinika: jej podstrony, O nas: rozdziały.
 * Ustawia też html[data-view], od którego zależą kolory kropkowego gradientu w tle.
 */
export function SectionBar() {
  const threads = useFeature('THREADS_ENABLED'), accounts = useFeature('ACCOUNTS_ENABLED');
  const pathname = usePathname() ?? '/';
  const params = useSearchParams();
  const router = useRouter();
  const tropy = pathname === '/' || pathname === '/spinki';
  const clinic = pathname.startsWith('/klinika') || pathname.startsWith('/raport') || pathname === '/metodologia';
  const view = tropy || pathname.startsWith('/spinki') ? 'tropy' : clinic ? 'klinika' : 'inne';
  useEffect(() => { document.documentElement.dataset.view = view; }, [view]);
  // kulka pod aktywną pozycją; przesuwanie kursora po pasku przesuwa ją płynnie (właściciel 3.10)
  const nav = useRef<HTMLElement>(null);
  const [dot, setDot] = useState<number | null>(null);
  const [sortOpen, setSortOpen] = useState(false);
  const place = (el: Element | null) => setDot(el instanceof HTMLElement ? el.offsetLeft + el.offsetWidth / 2 : null);
  const home = () => place(nav.current?.querySelector('[aria-current="page"]') ?? null);
  useLayoutEffect(() => { home(); }, [pathname, params?.toString()]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!sortOpen) return;
    const close = (event: Event) => { if (!(event.target as HTMLElement).closest?.('.sc-topbar__sort')) setSortOpen(false); };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setSortOpen(false); };
    document.addEventListener('click', close); window.addEventListener('keydown', key);
    return () => { document.removeEventListener('click', close); window.removeEventListener('keydown', key); };
  }, [sortOpen]);
  if (!threads) return null;

  const source = params?.get('zrodlo') ?? 'all';
  const sort = params?.get('sort') ?? 'hot';
  const query = (next: Record<string, string>) => {
    const search = new URLSearchParams(params?.toString());
    Object.entries(next).forEach(([key, value]) => { if (value === 'all' || value === 'hot') search.delete(key); else search.set(key, value); });
    const text = search.toString();
    return `${pathname}${text ? `?${text}` : ''}`;
  };

  let items: Item[] = [];
  if (tropy) {
    items = FEED_SOURCES.map(item => ({ label: item.label, href: query({ zrodlo: item.value }), current: source === item.value }));
    if (accounts) items.push({ label: 'Ułóż swoją spinkę', href: '/konto/spinki/nowa', current: false, accent: true });
  } else if (clinic) {
    items = clinicNavigation.map(item => ({ label: item.label, href: item.href, current: isClinicNavigationCurrent(pathname, item.href) }));
  } else if (pathname.startsWith('/konsylium')) {
    items = [{ label: 'Konsylium AI', href: '/konsylium', current: pathname === '/konsylium' }, { label: 'Karta Konsylium', href: '/konsylium/karta', current: pathname === '/konsylium/karta' },
      { label: 'Metodologia', href: '/metodologia', current: false }, { label: 'Rejestr korekt', href: '/klinika/korekty', current: false }];
  } else if (pathname === '/o-nas') {
    items = ABOUT.map(([id, label]) => ({ label, href: `/o-nas#${id}`, current: false }));
  }

  const sortLabel = FEED_SORTS.find(item => item.value === sort)?.label ?? 'Najgorętsze';
  return <nav ref={nav} className="sc-topbar" aria-label="Kategorie działu" data-count={items.length + (tropy ? 1 : 0)}
    onMouseOver={event => { const el = (event.target as HTMLElement).closest('a, .sc-topbar__sort'); if (el && nav.current?.contains(el)) place(el); }}
    onMouseLeave={home}>
    {items.map(item => <Link key={item.href + item.label} href={item.href} scroll={false} className={item.accent ? 'sc-topbar__accent' : undefined}
      aria-current={item.current ? 'page' : undefined}>{item.label}</Link>)}
    {tropy && <div className="sc-topbar__sort">
      {/* kolejność: rozwija się na czarnym tle, sam tekst i niedociągnięte linie (właściciel 3.10) */}
      <button type="button" aria-haspopup="listbox" aria-expanded={sortOpen} aria-label={`Kolejność spinek: ${sortLabel}`} onClick={() => setSortOpen(!sortOpen)}>
        {sortLabel} <span aria-hidden="true">⌄</span></button>
      {sortOpen && <ul className="sc-topbar__menu" role="listbox" aria-label="Kolejność spinek">
        {FEED_SORTS.map(item => <li key={item.value}><button type="button" role="option" aria-selected={item.value === sort}
          onClick={() => { setSortOpen(false); router.replace(query({ sort: item.value }), { scroll: false }); }}>{item.label}</button></li>)}
      </ul>}
    </div>}
    <span className="sc-topbar__dot" aria-hidden="true" hidden={dot === null} style={{ transform: `translateX(${dot ?? 0}px)` }} />
  </nav>;
}
