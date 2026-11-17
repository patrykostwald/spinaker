import { serverFeature } from '../../../lib/features';
import { redirect } from 'next/navigation';
import { AccountDelete } from '@spin-clinic/ui';
export const metadata = { title: 'Usuń konto - spin.clinic', robots: { index: false, follow: false } };
export default async function Page() {
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <AccountDelete />;
}
