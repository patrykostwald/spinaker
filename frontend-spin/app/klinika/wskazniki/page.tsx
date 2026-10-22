import type { Metadata } from 'next';
import { ClinicIndicators } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Wskaźniki Kliniki - spin.clinic',
  description: 'Ile wpisów polityków czyta i bada Dr. Spin: liczby, wykresy dzienne, techniki i obie strony obok siebie, zawsze z liczebnością próby.',
};

export default function ClinicIndicatorsRoute() {
  return <ClinicIndicators />;
}
