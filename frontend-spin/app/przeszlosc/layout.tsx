import type { Metadata, Viewport } from 'next';
import { PT_ICON, PT_THEME } from './pwa';
import { PtFx } from './PtFx';
import './v3.css';

/**
 * Segment przeszłość.today (port v3, 13.10): zakres stylów v3 (.pt-v3, akcent sepia), ikony i kolor paska dla PWA.
 * Na domenie przeszlosc.today każdy adres to /przeszlosc/* (middleware), więc metadane segmentu działają tylko na przeszłości,
 * a layout główny i manifest spin.clinic zostają bez zmian (bez headers() - strony nie przechodzą na renderowanie dynamiczne).
 */
export const metadata: Metadata = {
  icons: {
    icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }, { url: PT_ICON('favicon-32.png'), type: 'image/png', sizes: '32x32' }],
    shortcut: '/przeszlosc-icon.svg',
    apple: [{ url: PT_ICON('apple-touch-icon.png'), sizes: '180x180', type: 'image/png' }],
  },
  appleWebApp: { capable: true, title: 'przeszłość.today', statusBarStyle: 'black-translucent' },
};

export const viewport: Viewport = { themeColor: PT_THEME };

export default function PrzeszloscLayout({ children }: { children: React.ReactNode }) {
  return <div className="pt-v3" data-brand="przeszlosc"><PtFx />{children}</div>;
}
