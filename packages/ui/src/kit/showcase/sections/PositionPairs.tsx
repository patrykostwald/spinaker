"use client";

import { PositionPair, PositionPairs } from "../../PositionPair";
import { normalizePair, type PositionPairData } from "../../../lib/positionPairs";

export const meta = {
  id: "position-pairs",
  title: "Wcześniej i teraz: para wypowiedzi",
  lead: "Dwie wypowiedzi tej samej osoby o tym samym temacie, obok siebie, bez oceny. Ta sama miara dla każdej strony. Wszystkie dane w tej sekcji są FIKCYJNE (demo) i nie występują na produkcji; funkcja jest za flagą NEXT_PUBLIC_POSITION_PAIRS.",
};

const NOTICE = "Dwie wypowiedzi o tym samym temacie. Pokazujemy je obok siebie bez oceny. Sprawdź źródła i kontekst.";

/** Fikcyjne pary w kształcie kontraktu API-v3.md (sekcja 5); osoba, cytaty i adresy są wymyślone. */
const RAW = [
  {
    id: 9001, topic: "podatek od nieruchomości",
    a: { kind: "wpis", kind_label: "Wpis na X", date: "2025-03-04", quote: "Nie podniesiemy podatku od nieruchomości w tej kadencji.", vote: null,
      source: { name: "@konto_przykladowe na X (przykład)", url: "https://example.org/x/status/1", fetched_at: "2025-03-04" } },
    b: { kind: "glos", kind_label: "Głosowanie w Sejmie", date: "2026-09-26", quote: null, vote: "za",
      vote_subject: "Pkt 5. Rządowy projekt ustawy o podatkach i opłatach lokalnych - całość projektu",
      source: { name: "Sejm RP, głosowanie 41/12, kadencja 10 (przykład)", url: "https://example.org/sejm/glosowanie/41", fetched_at: "2026-09-26" } },
    context: "Projekt podnosi górną stawkę podatku od nieruchomości od 2027 roku.",
    approved_at: "2026-10-13T10:02:00+02:00", ai_suggested: true, notice: NOTICE, report_url: "/api/stanowiska/9001/zgloszenie/",
  },
  {
    id: 9002, topic: "wiek emerytalny",
    a: { kind: "wystapienie", kind_label: "Wystąpienie w Sejmie", date: "2024-05-17",
      quote: "Uważam, że obecny wiek emerytalny jest rozsądnym kompromisem i nie widzę potrzeby jego zmiany. Rozmowy o zmianach tylko wprowadzają niepokój wśród ludzi, którzy planują swoje życie na dziesięciolecia do przodu, i trzeba je zakończyć.",
      vote: null, source: { name: "Stenogram posiedzenia Sejmu (przykład)", url: "https://example.org/sejm/stenogram/12", fetched_at: "2024-05-20" } },
    b: { kind: "wypowiedz", kind_label: "Wypowiedź w wywiadzie", date: "2026-08-02",
      quote: "Jeśli demografia będzie wyglądać tak, jak pokazują dane, to rozmowa o wieku emerytalnym musi wrócić do stołu. Nie wolno jej unikać tylko dlatego, że jest niewygodna. Zależy mi na tym, żeby to była debata oparta na liczbach, z udziałem związków zawodowych, ekspertów i pracodawców, a nie na hasłach.",
      vote: null, source: { name: "Wywiad w serwisie informacyjnym (przykład)", url: "https://example.org/wywiad/emerytury", fetched_at: "2026-08-03" } },
    context: "", approved_at: "2026-10-12T09:15:00+02:00", ai_suggested: false, notice: NOTICE, report_url: "/api/stanowiska/9002/zgloszenie/",
  },
  {
    id: 9003, topic: "budowa elektrowni jądrowej",
    a: { kind: "wpis", kind_label: "Wpis na X", date: "2023-11-09", quote: "Atom to przyszłość polskiej energetyki.", vote: null,
      source: { name: "@konto_przykladowe na X (przykład)", url: "https://example.org/x/status/2", fetched_at: "2023-11-09" } },
    b: { kind: "wpis", kind_label: "Wpis na X", date: "2026-10-01", quote: "Koszt inwestycji jest dziś trzy razy wyższy, niż zakładano, więc projekt trzeba przeliczyć.", vote: null,
      source: { name: "@konto_przykladowe na X (przykład)", url: "https://example.org/x/status/3", fetched_at: "2026-10-01" } },
    context: "Wartość inwestycji zmieniła się po przetargu z września 2026 roku.", approved_at: "2026-10-13T08:00:00+02:00", ai_suggested: true, notice: NOTICE,
    report_url: "/api/stanowiska/9003/zgloszenie/",
  },
];

export const DEMO_PAIRS = RAW.map(normalizePair).filter((pair): pair is PositionPairData => pair !== null);

export function Section() {
  return <div className="sc-v3" style={{ display: "grid", gap: 48 }}>
    <p><span className="sc-v3-tag" data-tone="demo">Demo, fikcja</span></p>
    <PositionPairs block={{ items: DEMO_PAIRS, notice: NOTICE, paused: false }} id="demo-wczesniej-i-teraz" />
    <div style={{ maxWidth: 420 }}>
      <p className="sc-v3-pd__eb">Wąski kontener (telefon): A u góry, strzałka pionowo, B pod nim</p>
      <PositionPair pair={DEMO_PAIRS[1]} as="h3" reportable={false} />
    </div>
    <div style={{ maxWidth: 820 }}>
      <p className="sc-v3-pd__eb">Zestawienie w spince: etykiety boksów zamiast „Wcześniej” i „Teraz” (kolejność autora nie jest chronologią)</p>
      <PositionPair pair={DEMO_PAIRS[2]} as="h3" labels={["Boks 2", "Boks 3"]} notice="Autor spinki zestawił dwa materiały. Pokazujemy je obok siebie bez oceny. Sprawdź źródła i kontekst." reportable={false} />
    </div>
    <PositionPairs block={{ items: [], notice: NOTICE, paused: true }} id="demo-cisza" />
  </div>;
}
