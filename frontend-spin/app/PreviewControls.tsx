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
  return <footer className="sc-shell-footer">
    <div><Link href="/" className="sc-wordmark">spin.clinic</Link><p>iapply sp. z o.o.</p></div>
    <nav aria-label="Informacje o serwisie">{siteNavigation.footer.filter(column => column.title !== "Obserwuj").flatMap(column => column.links).filter(link => link.href !== "/").map(link => <Link key={link.href} href={link.href}>{link.label}</Link>)}</nav>
    <div className="sc-shell-footer__tools"><Link href="/wsparcie">Wesprzyj projekt</Link>{pathname?.startsWith('/klinika') && <HowToRead interview={pathname.startsWith('/klinika/wywiady')} />}{APP_ENABLED && <a href="#zainstaluj-aplikacje">Zainstaluj aplikację</a>}{APP_ENABLED && <Link href="/aplikacja">Aplikacja i alerty</Link>}{APP_ENABLED && PUSH_ENABLED && <a href="#powiadomienia">Powiadomienia</a>}</div>
    <a href="/en/about" lang="en" hrefLang="en">English</a>
  </footer>;
}
