import { AlertLink } from './AlertLink';

export const metadata = {
  title: 'Alerty - przeszłość.today',
  robots: { index: false, follow: false },
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function AlertsRoute() {
  return <AlertLink />;
}
