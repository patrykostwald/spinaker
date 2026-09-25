import type { Metadata } from 'next';
import { ClinicPage } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Klinika spinu — spin.clinic',
  description: 'Automatyczne diagnozy AI postów polityków z X: rządzący i opozycja według tych samych zasad, z wagą spinu i przekazami dnia.',
};

export default function ClinicRoute() {
  return <ClinicPage />;
}
