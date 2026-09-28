import { Suspense } from 'react';
import type { Metadata } from 'next';
import { HomePageSimple } from '@spin-clinic/ui/kit';

// Podgląd uproszczonej strony głównej (28.09.2026) — do porównania z obecną; ukryty przed wyszukiwarkami.
export const metadata: Metadata = { title: 'Nowa strona główna — podgląd · spin.clinic', robots: { index: false, follow: false } };

export default function NewHomePreview() { return <Suspense><HomePageSimple /></Suspense>; }
