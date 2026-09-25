import type { Metadata } from 'next';
import { ClinicQueue } from '@spin-clinic/ui';

export const metadata: Metadata = { title: 'Kolejka Kliniki — spin.clinic', robots: { index: false } };

export default function ClinicQueueRoute() {
  return <ClinicQueue />;
}
