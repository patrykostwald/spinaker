"use client";
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useFeature } from '../../lib/features';
import { useNotifications } from '../../lib/accountPhase2';

const entries = [
  { label: 'Start', href: '/', path: 'm3 11 9-8 9 8M5 10v11h14V10M9 21v-7h6v7' },
  { label: 'Tropy', href: '/tropy', path: 'M3 6h6v12H3zM15 6h6v12h-6zM9 12h6' },
  { label: 'Szukaj', href: '/search', path: 'M21 21l-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0' },
  { label: 'Powiadomienia', href: '/konto#powiadomienia', path: 'M18 8a6 6 0 0 0-12 0v7l-2 3h16l-2-3ZM10 21h4', account: true },
  { label: 'Profil', href: '/profile', path: 'M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 22v-3a8 8 0 0 1 16 0v3', account: true },
];

export function SocialNavigation() {
  const threads = useFeature('THREADS_ENABLED'), accounts = useFeature('ACCOUNTS_ENABLED'), app = useFeature('APP_ENABLED');
  const pathname = usePathname(), notifications = useNotifications();
  if (!threads) return null;
  return <nav className={`sc-social-navigation${app ? ' sc-social-navigation--app' : ''}`} aria-label="Nawigacja społeczności">
    {entries.map(entry => {
      const content = <><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={entry.path} /></svg>
        <span>{entry.label}</span>{entry.label === 'Powiadomienia' && Boolean(notifications.data?.unread) && <small aria-label={`${notifications.data!.unread} nieprzeczytanych`}>{notifications.data!.unread}</small>}</>;
      return entry.account && !accounts ? <span key={entry.label} aria-disabled="true" title="Dostępne po włączeniu kont">{content}</span> :
        <Link key={entry.label} href={entry.href} aria-current={pathname === entry.href ? 'page' : undefined}>{content}</Link>;
    })}
  </nav>;
}
