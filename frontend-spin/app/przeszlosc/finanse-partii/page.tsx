import { FinansePartiiPage } from './FinansePartiiPage';

export const metadata = {
  title: 'Finanse partii i komitetów (PKW) - przeszłość.today',
  description: 'Sprawozdania finansowe partii i komitetów wyborczych z pkw.gov.pl: szukaj po nazwie, zobacz decyzję PKW i kwoty odczytane z uchwał, otwórz oryginał.',
  robots: { index: false, follow: false },
};

export default function FinansePartiiRoute() {
  return <FinansePartiiPage />;
}
