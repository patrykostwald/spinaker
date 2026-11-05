import type { Metadata, Viewport } from 'next';
import { PT_ICON, PT_THEME } from './pwa';
import { PtFx } from './PtFx';
import { RetryFetch } from './RetryFetch';
import './v3.css';

/**
 * Segment przeszłość.today (port v3, 13.10): zakres stylów v3 (.pt-v3, akcent sepia), ikony i kolor paska dla PWA.
 * Na domenie przeszlosc.today każdy adres to /przeszlosc/* (middleware), więc metadane segmentu działają tylko na przeszłości,
 * a layout główny i manifest spin.clinic zostają bez zmian (bez headers() - strony nie przechodzą na renderowanie dynamiczne).
 */
// Runda person 1 (5.11): 7 z 10 person widziało w podglądzie i w tagach OG „spin.clinic - pokazujemy, jak zbudowany jest przekaz”
// (dziedziczone z layoutu głównego). Segment przeszłości ma własny opis, nazwę serwisu i obrazek (ikona; og.png jest marką spin.clinic).
const PT_TITLE = 'przeszłość.today - kto, co i kiedy w jednym temacie';
const PT_DESCRIPTION = 'Wypowiedzi polityków, głosowania Sejmu, spółki z KRS i pieniądze publiczne na jednej osi czasu. Tylko osoby i podmioty publiczne, każde powiązanie ze źródłem.';

export const metadata: Metadata = {
  metadataBase: new URL('https://przeszlosc.today'),
  description: PT_DESCRIPTION,
  openGraph: {
    type: 'website', siteName: 'przeszłość.today', locale: 'pl_PL', title: PT_TITLE, description: PT_DESCRIPTION,
    images: [{ url: '/przeszlosc/icon-512.png', width: 512, height: 512, alt: 'przeszłość.today' }],
  },
  twitter: { card: 'summary', title: PT_TITLE, description: PT_DESCRIPTION, images: ['/przeszlosc/icon-512.png'] },
  icons: {
    icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }, { url: PT_ICON('favicon-32.png'), type: 'image/png', sizes: '32x32' }],
    shortcut: '/przeszlosc-icon.svg',
    apple: [{ url: PT_ICON('apple-touch-icon.png'), sizes: '180x180', type: 'image/png' }],
  },
  appleWebApp: { capable: true, title: 'przeszłość.today', statusBarStyle: 'black-translucent' },
};

export const viewport: Viewport = { themeColor: PT_THEME };

export default function PrzeszloscLayout({ children }: { children: React.ReactNode }) {
  return <div className="pt-v3" data-brand="przeszlosc"><RetryFetch /><PtFx />{children}</div>;
}
