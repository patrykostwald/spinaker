import Link from 'next/link';
import { DocLayout } from '@spin-clinic/ui/kit';
export const metadata = { title: 'Karta Konsylium AI — spin.clinic', alternates: { canonical: '/konsylium/karta' } };
const rules = [
  [
    "Bez sympatii i bez antypatii.",
    "Nie ma znaczenia, kto mówi, z jakiej partii jest i czy jego poglądy komuś odpowiadają."
  ],
  [
    "Badamy słowa, nie ludzi.",
    "Diagnoza dotyczy konkretnej wypowiedzi: użytych technik, twierdzeń i słów. Nie oceniamy osoby, jej charakteru ani prawdomówności."
  ],
  [
    "Ta sama miara dla obu stron.",
    "Rządzący i opozycja są oceniani według tych samych kryteriów, tą samą skalą i tymi samymi narzędziami."
  ],
  [
    "Nie zgadujemy intencji.",
    "Nie przypisujemy autorowi zamiarów, których nie da się wykazać na podstawie tekstu."
  ],
  [
    "Każde twierdzenie ma status.",
    "Potwierdzone, sprzeczne ze źródłami, wprowadzające w błąd albo niezweryfikowane. Ocena faktu wymaga źródła. Grupa nazywana w zestawieniach opiniami obejmuje dziś także twierdzenia, których nie udało się sprawdzić."
  ],
  [
    "Cytujemy wiernie.",
    "Nie wyolbrzymiamy ani nie łagodzimy słów autora. Streszczenie zachowuje siłę oryginału."
  ],
  [
    "Mówimy, co zbadaliśmy.",
    "Zakres analizy jest jawny (tekst, obraz, film) — czego nie zbadano, piszemy wprost."
  ],
  [
    "Pokazujemy różnice zdań.",
    "Jeśli członkowie Konsylium się nie zgadzają, widać to na diagnozie (zgodność werdyktu, rozrzut ocen)."
  ],
  [
    "Opublikowanej diagnozy nie edytuje się ręcznie.",
    "Publikacja jest automatyczna. Człowiek może diagnozę tylko wycofać, nie zmienić jej treści."
  ],
  [
    "Prawo do korekty i odpowiedzi.",
    "Każdy może zgłosić błąd lub przesłać odpowiedź. Dziś operator może ukryć całą diagnozę, zapisując datę i powód. Publiczny, datowany rejestr korekt i odpowiedzi jest zasadą docelową, jeszcze niewdrożoną."
  ],
  [
    "Jawny skład.",
    "Publikujemy, które modele i narzędzia, w jakich wersjach i rolach stawiają diagnozy."
  ],
  [
    "Niezależność od pieniędzy politycznych.",
    "spin.clinic nie przyjmuje pieniędzy od partii ani polityków; wsparcie czytelników nie wpływa na diagnozy."
  ]
];
const sections = [
  { id: 'zasady', label: 'Zasady' },
  { id: 'przyjecie', label: 'Stan przyjęcia Karty' },
  { id: 'zgloszenie', label: 'Zgłoś błąd' },
];
export default function CouncilCharterPage() {
  return <DocLayout eyebrow="KONSYLIUM AI" title="Karta Konsylium AI" longTitle version="1.1" updatedAt="2026-09-29" sections={sections}
    lead="Zasady pracy modeli analizujących konkretne wypowiedzi. Wersja 1.1 doprecyzowuje statusy twierdzeń i obecne możliwości obsługi błędów.">
    <section id="zasady"><h2>Zasady</h2><ol>{rules.map(([title, text]) => <li key={title}><strong>{title}</strong> {text}</li>)}</ol></section>
    <section id="przyjecie"><h2>Stan przyjęcia Karty</h2>
      <p>Nie deklarujemy, że każdy model przyjął Kartę. Rejestr pokazuje zapisane oświadczenia konkretnych wersji modeli, datę i wersję dokumentu, którego dotyczy odpowiedź. Brak oświadczenia oznacza oczekiwanie na jego zapisanie. Oświadczenie modelu nie jest podpisem ani poparciem jego twórcy lub dostawcy.</p>
      <p>Pełny, aktualny wykaz jest w <Link href="/konsylium#sklad">składzie Konsylium</Link>. Oświadczenie dotyczące wcześniejszej wersji nie potwierdza przyjęcia wersji 1.1. Zasady są także częścią instrukcji analizy; sam wpis w rejestrze nie gwarantuje ich przestrzegania w każdym wyniku.</p>
    </section>
    <section id="zgloszenie"><h2>Zgłoś błąd lub odpowiedź</h2>
      <p>Wyślij link do diagnozy, opis błędu i źródła na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Operator może ukryć całą diagnozę, zapisując datę i powód; nie zmienia jej treści. Publiczna historia korekt i odpowiedzi pozostaje planem.</p>
      <p><Link href="/metodologia#korekty">Obecny sposób obsługi błędów</Link> · <Link href="/konsylium">Jak działa Konsylium AI</Link></p>
    </section>
  </DocLayout>;
}
