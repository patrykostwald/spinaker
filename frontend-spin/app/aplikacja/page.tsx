import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { serverFeature } from '../../lib/features';
import { AppGuide } from './AppGuide';

export const metadata: Metadata = {
  title: 'Aplikacja i alerty - spin.clinic',
  description: 'Zainstaluj spin.clinic na telefonie lub komputerze i włącz alerty o wpisach obserwowanych polityków.',
  alternates: { canonical: '/aplikacja' },
};

export default async function AppPage() {
  // Strona jest częścią aplikacji: jedna flaga NEXT_PUBLIC_APP_ENABLED (albo tryb podglądu).
  if (!(await serverFeature('APP_ENABLED'))) redirect('/');
  return <AppGuide />;
}
