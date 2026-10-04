"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useFeature } from '../../lib/features';
import { useAccount } from '../../lib/account';
import { useNotifications } from '../../lib/accountPhase2';
import { ThemeSwitcher } from '../ThemeSwitcher';
import { BugReportButton } from '../BugReport';
import { trackPage } from '../../lib/journey';

type Entry = { label: string; href: string; path: string; account?: boolean };
const icon = {
  tropy: 'M4 7h5v10H4zM15 7h5v10h-5zM9 12h6',
  clinic: 'M12 3v18M3 12h18M7 7h10v10H7z',
  search: 'M21 21l-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
  bell: 'M18 8a6 6 0 0 0-12 0v7l-2 3h16l-2-3ZM10 21h4',
  profile: 'M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 22v-3a8 8 0 0 1 16 0v3',
  council: 'M5 8a3 3 0 1 0 6 0 3 3 0 0 0-6 0M13 8a3 3 0 1 0 6 0 3 3 0 0 0-6 0M2 20a6 6 0 0 1 10-4.5A6 6 0 0 1 22 20',
  support: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
};
const main: Entry[] = [
  { label: 'Spinki', href: '/', path: icon.tropy },
  { label: 'Klinika', href: '/klinika', path: icon.clinic },
  { label: 'Szukaj', href: '/search', path: icon.search },
  { label: 'Profil', href: '/profile', path: icon.profile, account: true },
  { label: 'Powiadomienia', href: '/konto#powiadomienia', path: icon.bell, account: true },
];
const extra: Entry[] = [
  { label: 'Konsylium AI', href: '/konsylium', path: icon.council },
  { label: 'Wesprzyj nas', href: '/wsparcie', path: icon.support },
];
// Kolejność od najkrótszej nazwy do najdłuższej: równy „schodek” (właściciel 3.10: harmonia).
const small = [
  { label: 'O nas', href: '/o-nas' }, { label: 'Zasady', href: '/zasady-korzystania' }, { label: 'English', href: '/en/about', lang: 'en' },
  { label: 'Prywatność', href: '/polityka-prywatnosci' }, { label: 'Dla redakcji', href: '/dla-redakcji' }, { label: 'Metodologia', href: '/metodologia' },
];

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
}

function current(pathname: string, href: string) {
  if (href.includes('#')) return false;
  if (href === '/') return pathname === '/' || pathname.startsWith('/spinki');
  return pathname === href || pathname.startsWith(`${href}/`) || (href === '/klinika' && pathname.startsWith('/raport'));
}

function Wordmark() {
  return <Link href="/" className="sc-wordmark sc-rail__logo" aria-label="spin.clinic - strona główna"><span>spin<span aria-hidden="true">.</span>clinic</span><small className="sc-beta">BETA</small></Link>;
}

/**
 * Powłoka serwisu bez górnego menu (gdy działają tropy). Komputer: stały lewy pasek - logo, działy, pod kreską
 * Konsylium AI i Wesprzyj, na dole drobne linki. Telefon: cienki pasek u góry (logo, dzwonek, Wesprzyj)
 * i 5 pozycji na dole; reszta w arkuszu „Więcej”. Tryb pełnoekranowy tropu ukrywa wszystkie paski.
 */
export function SocialNavigation() {
  const threads = useFeature('THREADS_ENABLED'), accounts = useFeature('ACCOUNTS_ENABLED');
  const pathname = usePathname() ?? '/', notifications = useNotifications(), account = useAccount();
  const [sheet, setSheet] = useState(false);
  useEffect(() => setSheet(false), [pathname]);
  useEffect(() => trackPage(pathname), [pathname]);
  useEffect(() => {
    if (!sheet) return;
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setSheet(false); };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [sheet]);
  if (!threads) return null;
  const unread = notifications.data?.unread ?? 0;

  const item = (entry: Entry, compact = false) => {
    const content = <>{compact && <Icon d={entry.path} />}<span>{entry.label}</span>
      {entry.path === icon.bell && unread > 0 && <small className="sc-rail__badge" aria-label={`${unread} nieprzeczytanych`}>{unread}</small>}</>;
    if (entry.account && !accounts) return <span key={entry.label} aria-disabled="true" title="Dostępne po włączeniu kont">{content}</span>;
    return <Link key={entry.label} href={entry.href} className={compact ? undefined : entry.href === '/wsparcie' ? 'sc-rail__support' : undefined}
      aria-current={current(pathname, entry.href) ? 'page' : undefined}>{content}</Link>;
  };

  return <>
    <header className="sc-rail-top">
      <Wordmark />
      <div className="sc-rail-top__actions">
        {accounts && <Link href="/konto#powiadomienia" className="sc-rail-top__bell" aria-label={unread ? `Powiadomienia: ${unread} nieprzeczytanych` : 'Powiadomienia'}><Icon d={icon.bell} />{unread > 0 && <small className="sc-rail__badge">{unread}</small>}</Link>}
        <Link href="/wsparcie" className="sc-rail-top__support">Wesprzyj</Link>
      </div>
    </header>

    <nav className="sc-social-navigation sc-rail" aria-label="Działy serwisu">
      <Wordmark />
      <div className="sc-rail__group">{main.map(entry => item(entry))}</div>
      <hr />
      <div className="sc-rail__group">{extra.map(entry => item(entry))}</div>
      {accounts && !account.data?.authenticated && <Link href="/konto" className="sc-rail__login">Zaloguj się</Link>}
      <div className="sc-rail__foot">
        <ThemeSwitcher compact />
        <p>{small.map(link => link.lang ? <a key={link.href} href={link.href} lang={link.lang} hrefLang={link.lang}>{link.label}</a> : <Link key={link.href} href={link.href}>{link.label}</Link>)}<BugReportButton className="sc-rail__bug" /></p>
      </div>
    </nav>

    <nav className="sc-tabbar" aria-label="Działy serwisu">
      {[main[0], main[1], main[2], main[3]].map(entry => item(entry, true))}
      <button type="button" aria-expanded={sheet} aria-controls="sc-more-sheet" onClick={() => setSheet(value => !value)}><Icon d={icon.more} /><span>Więcej</span></button>
    </nav>

    {sheet && <div className="sc-more-sheet" onClick={event => { if (event.target === event.currentTarget) setSheet(false); }}>
      <div id="sc-more-sheet" role="dialog" aria-modal="true" aria-label="Więcej" className="sc-more-sheet__panel">
        <div className="sc-rail__group">{extra.map(entry => item(entry))}</div>
        <p>{small.map(link => link.lang ? <a key={link.href} href={link.href} lang={link.lang} hrefLang={link.lang}>{link.label}</a> : <Link key={link.href} href={link.href}>{link.label}</Link>)}</p>
        <ThemeSwitcher compact />
        <BugReportButton className="sc-rail__bug" />
        <button type="button" className="sc-more-sheet__close" onClick={() => setSheet(false)}>Zamknij</button>
      </div>
    </div>}
  </>;
}
