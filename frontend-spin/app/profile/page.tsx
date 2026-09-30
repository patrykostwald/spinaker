import { serverFeature } from '../../lib/features';
import { redirect } from 'next/navigation';
export default async function ProfilePage() {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  redirect('/konto');
}
