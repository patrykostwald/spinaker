"use client";
import { useEffect } from 'react';
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

  return <nav className="sc-topbar" aria-label="Kategorie działu" data-count={items.length + (tropy ? 1 : 0)}>
    {items.map(item => <Link key={item.href + item.label} href={item.href} scroll={false} className={item.accent ? 'sc-topbar__accent' : undefined}
      aria-current={item.current ? 'page' : undefined}>{item.label}</Link>)}
    {tropy && <label className="sc-topbar__sort"><span className="sc-sr-only">Kolejność spinek</span>
      <select value={sort} onChange={event => router.replace(query({ sort: event.target.value }), { scroll: false })}>
        {FEED_SORTS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></label>}
  </nav>;
}
