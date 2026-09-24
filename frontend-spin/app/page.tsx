import { Suspense } from 'react';
import { HomePage } from '@spin-clinic/ui/kit';

// Etap 2, krok 1: strona główna na kicie (packages/ui/src/kit/home). Stary `PortalHome`
// zostaje w pakiecie do czasu przeniesienia pozostałych tras.
export default function Home() { return <Suspense><HomePage /></Suspense>; }
