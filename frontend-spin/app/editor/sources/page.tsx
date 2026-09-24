import { Suspense } from 'react';
import { SourcesCatalog } from '@spin-clinic/ui';
export default function SourcesPage() { return <Suspense fallback={<p>Ładuję katalog…</p>}><SourcesCatalog /></Suspense>; }
