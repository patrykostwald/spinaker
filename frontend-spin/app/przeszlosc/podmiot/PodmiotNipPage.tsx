"use client";
import { Bar, Foot, useStandalone } from '../ui';
import { PodmiotNip } from '../PodmiotNip';

/** Strona „Podmiot po NIP” (6.11.2026): gminy i inne podmioty bez KRS; ogłoszenia BZP/TED i dotacje FTS powiązane wyłącznie po NIP. */
export function PodmiotNipPage({ nip }: { nip: string }) {
  useStandalone();
  return <div className="px pt-page">
    <Bar />
    <PodmiotNip nip={nip} />
    <Foot />
  </div>;
}
