import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { serverFeature } from '../../../lib/features';
import { AplikacjaPage } from './AplikacjaPage';

/**
 * Aplikacja przeszłość.today (port v3, PWA seria 2): przewodnik instalacji. Jak /aplikacja na spin.clinic jest częścią
 * aplikacji: jedna flaga NEXT_PUBLIC_APP_ENABLED (albo tryb podglądu), bez niej przekierowanie na stronę główną przeszłości.
 * Na domenie przeszlosc.today adres to /aplikacja (middleware), canonical wskazuje właśnie ten adres.
 */
export const metadata: Metadata = {
  title: 'Aplikacja przeszłość.today - instalacja na telefonie i komputerze',
  description: 'Zainstaluj przeszłość.today jak aplikację: Android, iPhone i komputer. Co działa bez internetu i jak działają alerty e-mail.',
  alternates: { canonical: 'https://przeszlosc.today/aplikacja' },
};

export default async function AplikacjaRoute() {
  if (!(await serverFeature('APP_ENABLED'))) redirect('/przeszlosc');
  return <AplikacjaPage />;
}
