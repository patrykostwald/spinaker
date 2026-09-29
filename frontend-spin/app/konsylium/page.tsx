import Link from "next/link";
import { CouncilRoster, HowItWorksFilm } from "@spin-clinic/ui";
import { DocLayout } from "@spin-clinic/ui/kit";

export const metadata = {
  title: "Konsylium AI — spin.clinic",
  description: "Droga wpisu do diagnozy, aktualny skład Konsylium AI, oświadczenia modeli i narzędzia używane w analizie.",
  alternates: { canonical: "/konsylium" },
};

const sections = [
  { id: "droga-wpisu", label: "Droga wpisu" },
  { id: "sklad", label: "Skład i oświadczenia" },
  { id: "narzedzia", label: "Narzędzia" },
  { id: "roznice", label: "Różnice ocen" },
  { id: "zasady", label: "Zasady i błędy" },
  { id: "film", label: "Film" },
];

export default function CouncilPage() {
  return <DocLayout eyebrow="KONSYLIUM AI" title="Co zrobiliśmy z AI" version="1.0" updatedAt="2026-09-29" sections={sections}
    lead="Dr. Spin korzysta z kilku modeli, które osobno badają tę samą wypowiedź. Pokazujemy ich głosy, źródła, zakres analizy i ograniczenia.">
    <section id="droga-wpisu"><h2>Droga wpisu do diagnozy</h2>
      <ol className="sc-doc-steps">
        <li><strong>Strażnik.</strong> Wstępnie ocenia tekst wpisu z obserwowanego konta. Wynik selekcji kieruje wpis do kolejki, dalszej decyzji albo pominięcia; nie jest diagnozą.</li>
        <li><strong>Badania laboratoryjne.</strong> Słowa nacechowane, wydźwięk i obraźliwość to pomocnicze sygnały. Laboratorium może także szukać istniejących fact-checków, danych GUS i cytatów. Część badań wymaga już wyodrębnionych twierdzeń, więc w obecnym procesie uruchamia się po głosach Konsylium i wyszukiwaniu dowodów.</li>
        <li><strong>Konsylium.</strong> Modele niezależnie wskazują werdykt, siłę spinu, techniki z cytatami i twierdzenia do sprawdzenia. Agregacja łączy oceny według stałych reguł.</li>
        <li><strong>Dowody.</strong> Wyszukiwanie dostarcza źródeł do twierdzeń. Brak źródła oznacza brak weryfikacji, a nie fałsz. Materiały znalezione przez laboratorium uzupełniają źródła; same nie zmieniają werdyktu.</li>
        <li><strong>Przewodniczący, językoznawca i recenzent.</strong> Przewodniczący pisze uzasadnienie na podstawie ocen i dowodów. Recenzent sprawdza zgodność; jego uwagi mogą uruchomić jedną poprawkę tekstu przed publikacją. Językoznawca poprawia polszczyznę. Skład ról może się zmieniać.</li>
        <li><strong>Eskalacja.</strong> Płatna konsultacja Claude z wyszukiwaniem może zastąpić zwykłe sprawdzanie faktów, gdy zgodność spada poniżej 2/3 albo werdykt to „spin” z siłą co najmniej 70/100. Wymaga twierdzeń do sprawdzenia, włączonej usługi i wolnego budżetu. W kodzie odbywa się przed pisaniem uzasadnienia.</li>
        <li><strong>Publikacja.</strong> Domyślnie automatyczna, z oznaczeniem AI. Diagnoza zachowuje informacje o uczestnikach i ograniczeniach. Archiwizacja oryginalnego wpisu może przebiegać później, w tle.</li>
      </ol>
    </section>
    <section id="sklad"><h2>Aktualny skład i oświadczenia</h2>
      <p>Reguła docelowa to co najmniej 4 członków, co najmniej 3 firmy tworzące modele i co najmniej jeden model polski. Działa, gdy skonfigurowane modele odpowiadają i mają dostępne limity. Proces może zakończyć się przy 3 odpowiedziach, z informacją o ograniczonym składzie; mniej niż 3 odpowiedzi zatrzymuje diagnozę Konsylium.</p>
      <p>Poniżej jest aktualny rejestr modeli i ról, nie lista uczestników każdej historycznej diagnozy. Jej rzeczywisty skład sprawdzisz przy danym wyniku. Brak oświadczenia oznacza, że przyjęcie Karty nie zostało zapisane.</p>
      <CouncilRoster />
    </section>
    <section id="narzedzia"><h2>Narzędzia: działa i planowane</h2>
      <h3>Działa w obecnym procesie</h3>
      <ul>
        <li>Niezależne oceny Konsylium, agregacja, przewodniczący, recenzent i korekta językowa. Dostawcy oraz modele są pokazani w rejestrze powyżej; dostępność zależy od konfiguracji i limitów.</li>
        <li>Gemini z wyszukiwaniem Google oraz płatny Claude z wyszukiwaniem przy eskalacji. Do sprawdzenia twierdzeń trafiają odnośniki faktycznie zwrócone przez narzędzie wyszukiwania.</li>
        <li>Słownik polskich słów nacechowanych i wskazania modeli, 21 kategorii technik oraz kategoria „Inne”.</li>
        <li>HerBERT przez Hugging Face: wydźwięk i treści obraźliwe. Integracja bada krótki początek tekstu; wynik sygnalizuje skrócenie. Bez dostępu do usługi badanie jest pomijane.</li>
        <li>Google Fact Check Tools: odnajdywanie wcześniejszych sprawdzeń twierdzeń. Wynik innej redakcji jest źródłem do oceny, nie automatycznym werdyktem.</li>
        <li>GUS BDL: dopasowanie danych dla Polski, jednego roku i jednej z dwóch miar — stopy bezrobocia rejestrowanego lub przeciętnych miesięcznych wynagrodzeń brutto. Nie jest to uniwersalne sprawdzanie wszystkich liczb.</li>
        <li>Firecrawl: sprawdzenie obecności cytatu w pobranej treści źródła, do trzech par źródło–cytat na analizę, w limicie miesięcznym.</li>
        <li>Wayback Machine: próba zapisania publicznej kopii wpisu w kolejce działającej w tle. Kopia nie jest gwarantowana.</li>
      </ul>
      <p>Integracje laboratoryjne i archiwizacja wymagają odpowiednich dostępów. „Pominięto”, brak odpowiedzi albo wyczerpany limit nie oznaczają wykonanego badania. Samo istnienie integracji nie dowodzi, że użyto jej przy danej diagnozie.</p>
      <h3>Planowane rozszerzenia</h3>
      <ul>
        <li>Osobny detektor technik perswazji XLM-RoBERTa na własnej maszynie.</li>
        <li>Szersze, automatyczne sprawdzanie twierdzeń w Eurostacie, NBP oraz rejestrach prawa i instytucji. Obecne importowanie materiałów z Sejmu, ELI czy danych KRS nie jest takim mechanizmem weryfikacji każdej diagnozy.</li>
        <li>Dodatkowe płatne wyszukiwarki dowodów, np. Exa lub Tavily — do rozważenia, poza obecnym procesem Konsylium.</li>
      </ul>
    </section>
    <section id="roznice"><h2>Jak czytać różnice ocen</h2>
      <p>Przykład obliczenia, nie rzeczywista diagnoza: trzy modele oceniają materiał jako „częściowy spin”, a jeden jako „spin”; siły wynoszą 30, 40, 60 i 80. Wynik to „częściowy spin”, mediana siły 50/100, zgodność werdyktu 3/4 i rozrzut 30–80. Zgodność opisuje głosy modeli, nie prawdopodobieństwo prawdy.</p>
    </section>
    <section id="zasady"><h2>Zasady i zgłoszenia błędów</h2>
      <p><Link href="/metodologia">Metodologia</Link> wyjaśnia selekcję, obliczenia i ograniczenia. <Link href="/konsylium/karta">Karta Konsylium</Link> opisuje zasady pracy oraz stan ich przyjęcia przez modele.</p>
      <p>Błąd zgłoś z linkiem do diagnozy i źródłami na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Operator może wycofać diagnozę z publicznego widoku; nie edytuje jej treści. Publiczna historia korekt i odpowiedzi jest planowana.</p>
    </section>
    <section aria-labelledby="film-title"><h2 id="film-title">Zobacz, jak działa serwis</h2><HowItWorksFilm /></section>
  </DocLayout>;
}
