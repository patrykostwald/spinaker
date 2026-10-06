import { PilotPage } from './PilotPage';

export const metadata = {
  title: 'Pilotaż - przeszłość.today',
  description: 'Bezpłatny pilotaż dla dziennikarzy, redakcji i organizacji strażniczych: wszystkie funkcje, te same warunki dla wszystkich.',
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function PilotRoute() {
  return <PilotPage />;
}
