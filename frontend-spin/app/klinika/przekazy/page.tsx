import type { Metadata } from 'next';
import { ClinicMessageArchive } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Archiwum przekazów - Klinika spinu',
  description: 'Przekazy dnia Rządzących i Opozycji w jednym archiwum, dzień po dniu.',
};

export default function MessagesRoute() {
  return <ClinicMessageArchive />;
}
