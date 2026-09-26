import { redirect } from 'next/navigation';
import { PublicAccountProfile } from '@spin-clinic/ui';
export default function PublicProfilePage({ params }: { params: { username: string } }) {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  return <PublicAccountProfile username={params.username} />;
}
