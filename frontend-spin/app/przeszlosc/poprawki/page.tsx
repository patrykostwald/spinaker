import { Poprawki } from './Poprawki';

export const metadata = {
  title: 'Poprawki - przeszłość.today',
  description: 'Rejestr sprostowań przyjętych i wprowadzonych w przeszłość.today: data, rekord i nazwa, bez danych zgłaszających.',
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function PoprawkiRoute() {
  return <Poprawki />;
}
