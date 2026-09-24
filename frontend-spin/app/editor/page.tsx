import { Suspense } from 'react';
import { ThreadEditor } from '@spin-clinic/ui';
export default function EditorPage() { return <Suspense fallback={<p>Ładuję…</p>}><ThreadEditor /></Suspense>; }
