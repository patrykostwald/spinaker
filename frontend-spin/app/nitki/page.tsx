import type { Metadata } from 'next';
import { CommunityThreadsPage } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Nitki — spin.clinic',
  description: 'Nitki kontekstowe czytelników: sprawy ułożone z materiałów z Bazy spin.clinic i źródeł dodanych przez link.',
};

export default function ThreadsRoute() {
  return <CommunityThreadsPage />;
}
