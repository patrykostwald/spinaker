import { serverFeature } from '../../../lib/features';
import { redirect } from 'next/navigation';
import { PublicAccountProfile } from '@spin-clinic/ui';
export default async function PublicProfilePage({ params }: { params: { username: string } }) {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <PublicAccountProfile username={params.username} />;
}
