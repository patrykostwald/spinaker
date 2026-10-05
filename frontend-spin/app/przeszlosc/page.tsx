import { TopicTree } from './TopicTree';

export const metadata = {
  title: 'przeszłość.today - kto, co i kiedy w jednym temacie',
  robots: { index: false, follow: false },
  // własny znak (właściciel 6.10: „favicon zjechany”) - plik leży pod /przeszlosc-…, więc działa też na domenie przeszlosc.today
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function PrzeszloscPage() {
  return <TopicTree />;
}
