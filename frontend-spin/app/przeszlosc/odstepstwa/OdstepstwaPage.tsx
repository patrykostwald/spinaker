"use client";
import { Bar, Foot, useStandalone } from '../ui';
import { Odstepstwa } from '../Odstepstwa';

/** Osobna strona odstępstw (port v3, 13.10): cel skrótu „Odstępstwa” w aplikacji przeszłość.today i pozycja menu. Ta sama sekcja co na głównej. */
export function OdstepstwaPage() {
  useStandalone();
  return <div className="px pt-page">
    <Bar />
    <Odstepstwa standalone />
    <Foot />
  </div>;
}
