import { Poprawki } from './Poprawki';

export const metadata = {
  title: 'Poprawki - przeszłość.today',
  description: 'Rejestr sprostowań przyjętych i wprowadzonych w przeszłość.today: data, rekord i nazwa, bez danych zgłaszających.',
};

export default function PoprawkiRoute() {
  return <Poprawki />;
}
