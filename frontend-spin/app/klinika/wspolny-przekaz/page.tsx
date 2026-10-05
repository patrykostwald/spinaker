import type { Metadata } from 'next';
import { CoordinatedList } from './CoordinatedList';

export const metadata: Metadata = {
  title: 'Wspólny przekaz - Klinika spinu',
  description: 'Prawie identyczne zdania, które co najmniej 3 konta polityków napisały w ciągu 6 godzin. Te same progi dla wszystkich obozów.',
};

export default function CoordinatedRoute() {
  return <CoordinatedList />;
}
