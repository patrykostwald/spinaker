import { Suspense } from 'react';
import { PoliticalReview } from '@spin-clinic/ui';
export default function PoliticalReviewPage() { return <Suspense fallback={<p>Ładuję panel…</p>}><PoliticalReview /></Suspense>; }
