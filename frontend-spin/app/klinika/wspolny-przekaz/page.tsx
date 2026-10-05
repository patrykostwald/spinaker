import type { Metadata } from 'next';
import { CoordinatedList } from './CoordinatedList';

export const metadata: Metadata = {
  title: 'Ta sama fraza - Klinika spinu',
  // do czasu WSPOLNY_PRZEKAZ_PUBLIC strona jest tylko podglądem dla redakcji
  robots: process.env.NEXT_PUBLIC_WSPOLNY_PRZEKAZ_PUBLIC === 'true' ? undefined : { index: false, follow: false },
  description: 'Prawie identyczne zdania, które co najmniej 3 konta polityków napisały w ciągu 6 godzin. Te same progi dla wszystkich obozów.',
};

export default function CoordinatedRoute() {
  return <CoordinatedList />;
}
