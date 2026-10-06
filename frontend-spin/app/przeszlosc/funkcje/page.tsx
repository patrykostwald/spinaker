import { Funkcje } from './Funkcje';

export const metadata = {
  title: 'Co potrafi przeszłość.today',
  description: 'Wszystkie funkcje przeszłość.today z przykładami: temat, profil osoby, głosowania, KRS, ślad pieniędzy z UE, alerty i eksport. W becie bezpłatnie dla każdego.',
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function FunkcjeRoute() {
  return <Funkcje />;
}
