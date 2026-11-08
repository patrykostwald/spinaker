"use client";

import { CausalChain, type CausalStep } from "../../CausalChain";
import { SpinMeter } from "../../SpinMeter";
import { SpinRow } from "../../SpinRow";

export const meta = {
  id: "v3",
  title: "v3: miara, wiersz, ciąg przyczyn",
  lead: "Komponenty przeniesione z prototypu spin-v3. Wszystkie dane w tej sekcji są FIKCYJNE (demo) i nie występują na produkcji.",
};

/** Dane demonstracyjne łańcucha „Dr Spin wyjaśnia” - wyłącznie w witrynie (na produkcji komponent jest wyłączony flagą). */
const DEMO_CHAIN: CausalStep[] = [
  { kind: "fakt", text: "Ceny ropy na rynkach światowych rosną od trzech miesięcy.", source: { name: "raport rynku paliw (przykład)", date: "12 paź" } },
  { kind: "fakt", text: "Słabszy kurs waluty podnosi koszt importu paliwa.", source: { name: "tabela kursów (przykład)", date: "12 paź" } },
  { kind: "interpretacja", text: "Podatki są stałą częścią ceny; rząd decyduje tylko o tej części." },
  { kind: "spin", text: "Wpisy pomijają rynek i kurs, a całą podwyżkę przypisują jednemu podmiotowi.", technique: "pominięcie kontekstu" },
  { kind: "wniosek", text: "Wina jednego podmiotu pomija część łańcucha: rynek, kurs i podatki działają razem." },
];

export function Section() {
  return <div className="sc-v3" style={{ display: "grid", gap: 32 }}>
    <p><span className="sc-v3-tag" data-tone="demo">Demo, fikcja</span></p>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 24 }}>
      <SpinMeter value={18} bare />
      <SpinMeter value={52} bare />
      <SpinMeter value={81} bare />
    </div>
    <div style={{ maxWidth: 560 }}>
      <SpinMeter value={64} size="lg" models={[{ label: "Q", value: 58 }, { label: "N", value: 66 }, { label: "G", value: 71 }, { label: "M", value: 60 }]} />
    </div>
    <ol className="sc-v3-rows" style={{ maxWidth: 820 }}>
      <SpinRow href="#v3" name="Konto Przykładowe" kind="Diagnoza AI · Spin" title="Przykładowy tytuł diagnozy w pełnej długości, bez ucięcia" meta={["Konto Przykładowe", "12 paź 2026, 09:18", "#SPIN-0000"]} value={79} />
      <SpinRow href="#v3" name="Profil Demo" kind="Diagnoza AI · Bez spinu" title="Krótki tytuł" meta={["Profil Demo", "12 paź 2026, 22:13", "#SPIN-0001"]} value={8} index={1} />
    </ol>
    <div style={{ maxWidth: 620 }}>
      <p className="sc-v3-pd__eb">Dr Spin wyjaśnia</p>
      <CausalChain steps={DEMO_CHAIN} force />
    </div>
  </div>;
}
