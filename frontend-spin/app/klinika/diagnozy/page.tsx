import type { Metadata } from 'next';
import { Suspense } from 'react';
import { ClinicDatabase } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Baza diagnoz - Klinika spinu',
  description: 'Przeszukaj diagnozy Kliniki spinu według polityka, partii, werdyktu, techniki i siły spinu.',
};

export default function ClinicDatabaseRoute() {
  return <Suspense fallback={<p role="status">Wczytywanie bazy diagnoz…</p>}><ClinicDatabase /></Suspense>;
}
