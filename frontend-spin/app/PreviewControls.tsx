"use client";
import { useFeature, usePreview, SupportBar, siteNavigation } from '@spin-clinic/ui';
import { SiteFooter } from '@spin-clinic/ui/kit';
import { PwaControls } from './PwaControls';

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
  const APP_ENABLED = useFeature('APP_ENABLED');
  const PUSH_ENABLED = useFeature('PUSH_ENABLED');
  return (
          <SiteFooter
            brand={<strong>spin<span className="sc-wordmark__dot">.</span>clinic</strong>}
            cta={{ label: "Wesprzyj projekt", href: "/wsparcie" }}
            columns={APP_ENABLED ? [...siteNavigation.footer, { title: 'Aplikacja', links: [
              { label: 'Zainstaluj aplikację', href: '#zainstaluj-aplikacje' },
              ...(PUSH_ENABLED ? [{ label: 'Powiadomienia', href: '#powiadomienia' }] : []),
            ] }] : siteNavigation.footer}
            above={<SupportBar />}
            sticky
          />
  );
}
