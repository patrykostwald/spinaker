import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { serverFeature } from '../../../lib/features';
import { AlertSettings } from './AlertSettings';

export const metadata: Metadata = { title: 'Ustawienia alertów', robots: { index: false, follow: false } };

export default async function AlertSettingsPage() {
  if (!(await serverFeature('ACCOUNTS_ENABLED'))) redirect('/');
  return <AlertSettings />;
}
