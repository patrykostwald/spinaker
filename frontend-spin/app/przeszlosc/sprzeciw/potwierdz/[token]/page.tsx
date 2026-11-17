import { PotwierdzenieSprzeciwu } from './PotwierdzenieSprzeciwu';

export const metadata = {
  title: 'Potwierdzenie sprzeciwu - przeszłość.today',
  description: 'Potwierdzenie wniosku o sprzeciw wobec przetwarzania danych w przeszłość.today.',
  robots: { index: false, follow: false },
};

export default function PotwierdzenieRoute({ params }: { params: { token: string } }) {
  return <PotwierdzenieSprzeciwu token={params.token} />;
}
