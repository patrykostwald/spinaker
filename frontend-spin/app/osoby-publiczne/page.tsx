import type { Metadata } from 'next';
import { PublicFigureDirectory } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Osoby publiczne — spin.clinic',
  description: 'Profile osób publicznych: funkcja, oficjalne głosowania i relacje potwierdzone w publicznych źródłach.',
};

export default function PublicFiguresPage() {
  return <PublicFigureDirectory />;
}
