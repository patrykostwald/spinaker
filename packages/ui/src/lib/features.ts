"use client";
import { useEffect, useState } from 'react';

const publicFeatures = {
  ACCOUNTS_ENABLED: process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED === 'true',
  THREADS_ENABLED: process.env.NEXT_PUBLIC_THREADS_ENABLED === 'true',
  PUSH_ENABLED: process.env.NEXT_PUBLIC_PUSH_ENABLED === 'true',
  APP_ENABLED: process.env.NEXT_PUBLIC_APP_ENABLED === 'true',
};
export type FeatureName = keyof typeof publicFeatures;
export function isPreview() {
  return typeof document !== 'undefined' && document.cookie.split(';').some(value => value.trim() === 'sc_preview=1');
}
export function usePreview() {
  const [preview, setPreview] = useState(false);
  useEffect(() => { setPreview(isPreview()); }, []);
  return preview;
}
/** SSR and the first browser render agree; preview activates after mounting. */
export function useFeature(name: FeatureName) {
  const preview = usePreview();
  return publicFeatures[name] || preview;
}
// For non-rendering callers. React components must use useFeature.
export const ACCOUNTS_ENABLED = publicFeatures.ACCOUNTS_ENABLED || isPreview();
export const THREADS_ENABLED = publicFeatures.THREADS_ENABLED || isPreview();
export const PUSH_ENABLED = publicFeatures.PUSH_ENABLED || isPreview();
export const APP_ENABLED = publicFeatures.APP_ENABLED || isPreview();
