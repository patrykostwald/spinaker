import type { Metadata } from 'next';
import { Suspense } from 'react';
import { PublicFigureDirectory } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Osoby publiczne — spin.clinic',
  description: 'Profile osób publicznych: funkcja, oficjalne głosowania i relacje potwierdzone w publicznych źródłach.',
};

export default function PublicFiguresPage() {
  return (
    <Suspense fallback={<p role="status">Wczytywanie rejestru osób…</p>}>
      <PublicFigureDirectory />
    </Suspense>
  );
}
