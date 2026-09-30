import { redirect } from 'next/navigation';
import { AccountDelete } from '@spin-clinic/ui';
export const metadata = { title: 'Usuń konto — spin.clinic', robots: { index: false, follow: false } };
export default function Page() {
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  return <AccountDelete />;
}
