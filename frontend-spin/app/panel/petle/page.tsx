import type { Metadata, Viewport } from 'next';
import { PetlePanel } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Pętle · spin.clinic', robots: { index: false, follow: false },
  manifest: '/panel/manifest.webmanifest',
  appleWebApp: { capable: true, title: 'spin.clinic · Pętle', statusBarStyle: 'black-translucent' },
  icons: { apple: '/panel/icon-192.png', icon: '/panel/icon-192.png' },
};
export const viewport: Viewport = { themeColor: '#000000', width: 'device-width', initialScale: 1 };
export default function Page() { return <PetlePanel />; }
