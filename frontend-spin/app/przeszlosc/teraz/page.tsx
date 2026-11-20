import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { serverFeatureVerified } from '../../../lib/features';
import { parsuj } from './parametry';
import { parsujPowiaty } from './powiaty';
import { TerazPage } from './TerazPage';
// style osi czasu (Os.tsx) na poziomie trasy: testy renderujące TerazPage nie ładują arkuszy CSS
import './os.css';

/**
 * „Teraz”: mapa Polski na żywo z warstwami komunikatów służb i instytucji (Z6a) oraz widoki tabela i „Mój powiat” (Z6b). Za flagą NEXT_PUBLIC_TERAZ_ENABLED
 * (albo zweryfikowany tryb podglądu), bez niej przekierowanie na stronę główną przeszłości. Na domenie przeszlosc.today adres to /teraz
 * (middleware). Do publicznego startu strona nie jest indeksowana (noindex); właściciel zdejmuje to przy starcie.
 * Konfiguracja czytana na serwerze w czasie żądania (bez przebudowy):
 *  - NEXT_PUBLIC_TERAZ_PODKLAD_URL: adres pliku PMTiles z podkładem wektorowym (bez niego podkład zapasowy),
 *  - NEXT_PUBLIC_TERAZ_GLIFY_URL: szablon glifów PBF dla podpisów miejscowości (bez niego mapa jest bez podpisów),
 *  - NEXT_PUBLIC_TERAZ_PROBNE=1: tryb danych przykładowych (jak ?probne=1).
 */
export const metadata: Metadata = {
  title: 'Teraz - mapa komunikatów służb i instytucji | przeszłość.today',
  description: 'Mapa Polski z komunikatami służb i instytucji. Włączasz tylko warstwy, które chcesz widzieć; każdy punkt ma źródło, godzinę publikacji i odnośnik do oryginału.',
  alternates: { canonical: 'https://przeszlosc.today/teraz' },
  robots: { index: false, follow: false },
};

export default async function TerazRoute({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  // podgląd musi być zweryfikowany podpisem z Django (verifiedPreview), samo ciasteczko sc_preview nie wystarcza
  if (!(await serverFeatureVerified('TERAZ_ENABLED'))) redirect('/przeszlosc');
  const poczatkowy = parsuj(searchParams);
  const probne = poczatkowy.probne || process.env.NEXT_PUBLIC_TERAZ_PROBNE === '1';
  return <TerazPage
    poczatkowy={{ ...poczatkowy, probne }}
    poczatkowePowiaty={parsujPowiaty(searchParams)}
    podkladUrl={process.env.NEXT_PUBLIC_TERAZ_PODKLAD_URL || ''}
    glifyUrl={process.env.NEXT_PUBLIC_TERAZ_GLIFY_URL || ''} />;
}
