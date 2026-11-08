import { Suspense } from 'react';
import { SocialPasswordSetup } from '@spin-clinic/ui';
export const metadata = { title: 'Ustaw hasło · spin.clinic', robots: { index: false, follow: false }, referrer: 'no-referrer' as const };
export default function Page() { return <Suspense fallback={<p>Wczytywanie…</p>}><SocialPasswordSetup /></Suspense>; }
