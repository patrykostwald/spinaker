import { redirect } from 'next/navigation';
import { AccountProfile } from '@spin-clinic/ui';
export default function ProfilePage() {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  return <AccountProfile />;
}
