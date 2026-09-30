import { serverFeature } from '../../lib/features';
import { redirect } from 'next/navigation';
import type { Metadata } from 'next';
import { CommunityThreadsPage } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Nitki — spin.clinic',
  description: 'Nitki kontekstowe czytelników: sprawy ułożone z materiałów z Bazy spin.clinic i źródeł dodanych przez link.',
};

export default async function ThreadsRoute({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  // Nitki czytelników wracają w fazie II (NEXT_PUBLIC_THREADS_ENABLED=true).
  if (!(await serverFeature('THREADS_ENABLED'))) redirect('/');
  const positiveId = (value: string | string[] | undefined) => typeof value === 'string' && /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : undefined;
  return <CommunityThreadsPage context={{ article_id: positiveId(searchParams.article_id), figure_id: positiveId(searchParams.figure_id), url: typeof searchParams.url === 'string' ? searchParams.url : undefined }} />;
}
