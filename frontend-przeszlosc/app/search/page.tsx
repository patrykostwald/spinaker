"use client";
import { Suspense } from 'react';
import { SearchPageContent } from '@spin-clinic/ui';
export default function SearchPage() {
  return <Suspense fallback={<p>Ładuję wyszukiwarkę…</p>}><SearchPageContent /></Suspense>;
}
