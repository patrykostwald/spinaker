/** Słowniczek pojęć serwisu: jedno źródło definicji dla /metodologia#slowniczek i podpowiedzi przy pojęciach (`Term`). */
export type GlossaryEntry = { id: string; term: string; definition: string };

export const GLOSSARY: readonly GlossaryEntry[] = [
  { id: "spin", term: "Spin", definition: "Sposób przedstawienia informacji, który ma wpłynąć na odbiorcę, np. pominięcie kontekstu, straszenie czy etykietowanie. Nie oznacza automatycznie kłamstwa." },
  { id: "dr-spin", term: "Dr. Spin", definition: "Nazwa naszej analizy wpisów polityków: Strażnik wybiera wpisy, Konsylium AI je ocenia, a wynik publikujemy jako diagnozę." },
  { id: "konsylium", term: "Konsylium AI", definition: "Kilka modeli AI różnych firm, które osobno oceniają ten sam wpis według wspólnych zasad, takich samych dla rządu i opozycji." },
  { id: "wersja-instrukcji", term: "Wersja instrukcji", definition: "Numer (np. v7) instrukcji, według której modele oceniały wpis. Gdy zmieniamy zasady oceny, numer rośnie, więc starsze diagnozy da się odróżnić od nowszych." },
  { id: "straznik", term: "Strażnik", definition: "Automatyczny filtr: czyta nowe wpisy polityków i wybiera te, w których jest teza do sprawdzenia. Jego wstępny wynik to nie jest siła spinu." },
  { id: "rekruter", term: "Rekruter", definition: "Mechanizm, który co noc sprawdza darmowe modele AI i proponuje nowego członka Konsylium. Kandydat najpierw zdaje egzamin na tych samych wpisach." },
  { id: "sila-spinu", term: "Siła spinu", definition: "Liczba od 0 do 100: nasilenie rozpoznanych zabiegów perswazji we wpisie. To nie procent fałszu i nie ocena osoby." },
  { id: "diagnoza", term: "Diagnoza", definition: "Pojedyncza analiza jednego wpisu: werdykt, siła spinu, rozpoznane techniki oraz twierdzenia sprawdzone ze źródłami." },
  { id: "przekaz-dnia", term: "Przekaz dnia", definition: "Zbiorcze podsumowanie tego, co danego dnia komunikowały konta jednej strony (rządzących albo opozycji): główne tematy i sposób argumentacji." },
  { id: "nitka", term: "Nitka", definition: "Zestaw materiałów (artykułów, wywiadów, filmów) ułożonych w oś czasu wokół jednego wydarzenia, żeby było widać kontekst." },
  { id: "os-czasu", term: "Oś czasu", definition: "Układ materiałów od najstarszego do najnowszego. Pokazuje, co było wcześniej, a co później." },
  { id: "box", term: "Box", definition: "Pojedyncza karta z jednym materiałem w nitce lub na osi czasu. W nitce pierwszy box (otwierający) to materiał, wokół którego budujemy kontekst." },
  { id: "zatwierdzono", term: "Zatwierdzono", definition: "Operator serwisu przejrzał analizę i zdecydował o jej publikacji. Nie edytuje treści: może ją tylko zatwierdzić albo odrzucić. Analizy bez tego oznaczenia publikują się automatycznie i są tak opisane." },
  { id: "do-decyzji", term: "Do decyzji operatora", definition: "Wstępny wynik Strażnika w przedziale 40-75: wpis czeka, aż operator zdecyduje, czy go zbadać. Niższe wyniki pomijamy, wyższe trafiają do automatycznej kolejki." },
];

export const glossaryEntry = (id: string): GlossaryEntry | undefined => GLOSSARY.find(entry => entry.id === id);
