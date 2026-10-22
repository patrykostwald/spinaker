import type { Metadata } from 'next';
import { ClinicCorrections } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Rejestr korekt – Klinika spinu',
  description: 'Publiczny rejestr wycofanych diagnoz, ukryć prawnych i odpowiedzi autorów wypowiedzi.',
};

export default function CorrectionsRoute() {
  return <ClinicCorrections />;
}
