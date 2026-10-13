"use client";
import { useFeature, usePreview, siteNavigation } from '@spin-clinic/ui';
import { usePathname } from 'next/navigation';
import { HowToRead } from '@spin-clinic/ui';
import { PwaControls } from './PwaControls';
import Link from 'next/link';

export function PreviewBanner() {
  const preview = usePreview();
  return preview ? <aside className="sc-preview-banner" aria-label="Tryb podglądu">
    <a href="/podglad">Tryb podglądu</a> · <a href="/api/preview/off/">Wyjdź</a>
  </aside> : null;
}
export function PreviewPwa() {
  const enabled = useFeature('APP_ENABLED');
  return enabled ? <PwaControls /> : null;
}
export function FeatureFooter() {
  const pathname = usePathname();
  const APP_ENABLED = useFeature('APP_ENABLED');
  const PUSH_ENABLED = useFeature('PUSH_ENABLED');
  // Przy tropach dolnego paska nie ma: linki i „Wesprzyj” są w lewym pasku (SocialNavigation).
  if (useFeature('THREADS_ENABLED')) return null;
  // v3 (13.10.2026): stopka w kolumnach z nagłówkami, notą o ocenie AI i operatorze; te same odnośniki co wcześniej.
  return <footer className="sc-shell-footer sc-v3-foot">
    <div className="sc-v3-foot__about">
      <Link href="/" className="sc-wordmark">spin.clinic</Link>
      <p className="sc-v3-foot__ai">Ocena AI, nie ustalenie faktów. Siła spinu to nasilenie technik perswazji w jednym wpisie, nie procent fałszu i nie miara winy. Ta sama miara dla wszystkich partii.</p>
      <p>Operator: iapply sp. z o.o.</p>
      <div className="sc-shell-footer__tools"><Link href="/wsparcie">Wesprzyj projekt</Link>{pathname?.startsWith('/klinika') && <HowToRead interview={pathname.startsWith('/klinika/wywiady')} />}{APP_ENABLED && <a href="#zainstaluj-aplikacje">Zainstaluj aplikację</a>}{APP_ENABLED && <Link href="/aplikacja">Aplikacja i alerty</Link>}{APP_ENABLED && PUSH_ENABLED && <a href="#powiadomienia">Powiadomienia</a>}</div>
    </div>
    {siteNavigation.footer.filter(column => column.title !== "Obserwuj").map(column => <nav key={column.title} aria-label={column.title}>
      <h2>{column.title}</h2>
      <ul>{column.links.filter(link => link.href !== "/").map(link => <li key={link.href}><Link href={link.href}>{link.label}</Link></li>)}</ul>
    </nav>)}
    <a className="sc-v3-foot__en" href="/en/about" lang="en" hrefLang="en">English</a>
  </footer>;
}
