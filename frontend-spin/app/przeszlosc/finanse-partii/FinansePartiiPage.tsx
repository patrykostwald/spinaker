"use client";
import { Bar, Foot, useStandalone } from '../ui';
import { FinansePartii } from '../FinansePartii';

/** Osobna strona „Finanse partii i komitetów (PKW)” (6.11.2026): spis sprawozdań z pkw.gov.pl ze streszczeniem uchwał PKW. */
export function FinansePartiiPage() {
  useStandalone();
  return <div className="px pt-page">
    <Bar />
    <FinansePartii />
    <Foot />
  </div>;
}
