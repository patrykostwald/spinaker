import type { Metadata, Viewport } from 'next';
import { SocialPanel } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Social media · spin.clinic', robots: { index: false, follow: false },
  manifest: '/panel/manifest.webmanifest',
  appleWebApp: { capable: true, title: 'spin.clinic · Social', statusBarStyle: 'black-translucent' },
  icons: { apple: '/panel/icon-192.png', icon: '/panel/icon-192.png' },
};
export const viewport: Viewport = { themeColor: '#000000', width: 'device-width', initialScale: 1 };
export default function Page() { return <SocialPanel />; }
