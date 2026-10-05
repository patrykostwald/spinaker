import { notFound } from 'next/navigation';
import { PersonProfile } from '../../PersonProfile';

export const metadata = {
  title: 'Osoba publiczna - przeszłość.today',
  description: 'Funkcje, wpisy z diagnozami Dr. Spina, dokumenty Sejmu, głosowania, KRS i wspólne mianowniki jednej osoby publicznej.',
  robots: { index: false, follow: false },
  icons: { icon: [{ url: '/przeszlosc-icon.svg', type: 'image/svg+xml' }], shortcut: '/przeszlosc-icon.svg', apple: '/przeszlosc-icon.svg' },
};

export default function PersonRoute({ params }: { params: { slug: string } }) {
  // adres: /przeszlosc/osoba/123-imie-nazwisko albo /przeszlosc/osoba/123
  if (!/^[1-9]\d{0,9}(-[a-z0-9-]{1,120})?$/.test(params.slug)) notFound();
  return <PersonProfile ident={params.slug} />;
}
