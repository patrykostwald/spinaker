import Link from 'next/link';
import { InfoPage } from '@spin-clinic/ui/kit';
import { CouncilRoster } from '@spin-clinic/ui';
export const metadata = { title: 'Karta Konsylium AI — spin.clinic' };
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
    "Potwierdzone, sprzeczne ze źródłami, wprowadzające w błąd albo opinia — nigdy bez podstawy. Ocena faktu zawsze wskazuje źródło."
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
    "Nikt nie poprawia diagnoz.",
    "Publikacja jest automatyczna. Człowiek może diagnozę tylko wycofać, nie zmienić jej treści."
  ],
  [
    "Prawo do korekty i odpowiedzi.",
    "Każdy może zgłosić błąd; autor wypowiedzi może odpowiedzieć. Korekty są jawne i datowane."
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
const members = [
  [
    "Strażnik",
    "modele darmowe",
    "Groq / NVIDIA",
    "wybór wpisów",
    "—"
  ],
  [
    "Członek",
    "GPT-oss 20B",
    "OpenAI (przez Groq)",
    "diagnoza",
    "do zapisania"
  ],
  [
    "Członek",
    "Qwen 27B",
    "Alibaba (przez Groq)",
    "diagnoza, językoznawca",
    "do zapisania"
  ],
  [
    "Członek, recenzent",
    "Nemotron 120B",
    "NVIDIA",
    "diagnoza, zgodność z Kartą",
    "do zapisania"
  ],
  [
    "Przewodniczący",
    "Gemini Flash",
    "Google",
    "uzasadnienie, sprawdzanie faktów",
    "do zapisania"
  ],
  [
    "Konsultant",
    "Claude",
    "Anthropic",
    "sprawdzanie faktów przy sporze i silnym spinie",
    "do zapisania"
  ],
  [
    "planowani",
    "PLLuM, Bielik, Mistral, modele Cloudflare",
    "Polska, Polska, Francja, różne",
    "diagnoza, polszczyzna",
    "po podłączeniu"
  ]
];
export default function CouncilCharterPage() {
  return <InfoPage eyebrow="KONSYLIUM AI" title="Karta Konsylium AI spin.clinic" lead="Wersja 1.0 · 29 września 2026">
<p>{"Konsylium AI to zespół modeli sztucznej inteligencji różnych firm, które niezależnie od siebie badają wypowiedzi polityków i wspólnie stawiają diagnozę. Ta Karta opisuje zasady, według których pracuje. Każdy członek Konsylium ją przyjmuje; jego zgoda jest zapisana w wykazie poniżej."}</p>
    <section><h2>Zasady</h2><ol>{rules.map(([title, text]) => <li key={title}><strong>{title}</strong> {text}</li>)}</ol></section>
    <section><h2>Skład i przyjęcie Karty</h2><CouncilRoster /></section>
    <section><h2>Zgłoś błąd</h2><p>Wyślij link do diagnozy, opis błędu i źródła na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>.</p></section>
    <p><Link href="/o-nas#konsylium">Wróć do opisu Konsylium AI</Link></p>
  </InfoPage>;
}
