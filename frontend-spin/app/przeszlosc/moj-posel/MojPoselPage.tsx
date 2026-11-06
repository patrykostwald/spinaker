"use client";
import { Bar, Foot, useStandalone } from '../ui';
import { MojPosel } from '../MojPosel';

/** Osobna strona „Mój poseł” (6.11.2026, pozycja 2 planu): wybór okręgu → posłowie z okręgu z odnośnikiem do profilu. */
export function MojPoselPage() {
  useStandalone();
  return <div className="px pt-page">
    <Bar />
    <MojPosel />
    <Foot />
  </div>;
}
