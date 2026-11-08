import { GlosowaniaPage } from './GlosowaniaPage';

export const metadata = {
  title: 'Głosowania Sejmu - przeszłość.today',
  description: 'Tabela głosowań imiennych Sejmu z naszej bazy: wynik ogółem, głos wybranego klubu i odnośnik do źródła. To nie jest pełne archiwum.',
  robots: { index: false, follow: false },
};

export default function GlosowaniaRoute() {
  return <GlosowaniaPage />;
}
