import Link from "next/link";
import { DocLayout } from "@spin-clinic/ui/kit";

export const metadata = {
  title: "Metodologia — spin.clinic",
  description: "Jak wybieramy wpisy, łączymy oceny AI i liczymy dane Kliniki. Zakres, ograniczenia i zasady zgłaszania błędów.",
  alternates: { canonical: "/metodologia" },
};

const sections = [
  { id: "selekcja", label: "Selekcja wpisów" }, { id: "zakres", label: "Zakres analizy" },
  { id: "werdykty", label: "Werdykty i siła" }, { id: "zgodnosc", label: "Zgodność modeli" },
  { id: "twierdzenia", label: "Statusy twierdzeń" }, { id: "techniki", label: "Rodziny technik" },
  { id: "slowa", label: "Słowa nacechowane" }, { id: "wykresy", label: "Mianowniki wykresów" },
  { id: "ograniczenia", label: "Ograniczenia" }, { id: "korekty", label: "Błędy i wycofanie" },
];

export default function MethodologyPage() {
  return <DocLayout eyebrow="METODOLOGIA" title="Jak analizujemy przekaz" longTitle version="1.0" updatedAt="2026-09-29" sections={sections}
    lead="Opis obecnego sposobu analizy wpisów i liczenia danych Kliniki. Diagnoza dotyczy konkretnego komunikatu; nie jest oceną osoby ani jej prawdomówności.">
    <section id="selekcja"><h2>Selekcja wpisów</h2>
      <p>Materiał pochodzi z obserwowanych, włączonych kont X polityków i partii. Strażnik analizuje dostępne wpisy z ostatnich dni; domyślne okno to 3 dni. Wstępny wynik wybiera kandydatów do pełnej analizy i nie jest siłą spinu z diagnozy.</p>
      <p>Domyślnie wynik selekcji od 40 oznacza wpis do dalszej decyzji, a od 75 kieruje go do kolejki automatycznej. Progi można skonfigurować. Dostępny budżet, limity usług, kolejka i dobór materiałów z obu obozów ograniczają liczbę diagnoz. Osobne miejsce może otrzymać popularny wpis dnia.</p>
      <p>To próba wybranych wypowiedzi, nie wszystkich wpisów ani całej debaty. Większa liczba diagnoz jednego obozu nie dowodzi większej skłonności do spinu. Brak diagnozy nie oznacza oceny „bez spinu”.</p>
    </section>
    <section id="zakres"><h2>Zakres analizy</h2>
      <p>Podstawą jest tekst wpisu. Kontekst może zawierać opisy dołączonych zdjęć i grafik, odczytany z nich tekst oraz tytuły i opisy podlinkowanych stron. Dostępność obrazu w materiale nie gwarantuje, że model skutecznie go zbadał. Braki opisujemy w ograniczeniach diagnozy.</p>
      <p>Film dołączony do wpisu nie jest automatycznie analizowany w tym procesie. <Link href="/klinika/wywiady">Analizy wywiadów</Link> mają osobny proces oparty na transkrypcji oraz osobne oceny gościa i prowadzącego. Wyników tych nie należy mieszać ze statystyką wpisów.</p>
    </section>
    <section id="werdykty"><h2>Werdykty i siła 0–100</h2>
      <dl className="sc-doc-definitions">
        <div><dt>Spin</dt><dd>W komunikacie rozpoznano wyraźne techniki perswazji lub manipulacyjnego przedstawiania treści.</dd></div>
        <div><dt>Częściowy spin</dt><dd>Takie elementy występują, lecz nie określają całego komunikatu w równym stopniu.</dd></div>
        <div><dt>Bez spinu</dt><dd>Analiza nie wykazała istotnego spinu w dostępnym materiale. Nie jest to certyfikat prawdziwości.</dd></div>
        <div><dt>Nie da się ocenić</dt><dd>Dostępne dane nie pozwalają rozstrzygnąć oceny.</dd></div>
      </dl>
      <p>Siła spinu 0–100 jest oceną nasilenia rozpoznanych zabiegów, nie procentem fałszu, pewności ani winy. Konsylium liczy medianę sił modeli z rozstrzygniętym werdyktem. Przy parzystej liczbie ocen jest to średnia dwóch środkowych wartości, sprowadzona do liczby całkowitej. Dla „bez spinu” wynik nie przekracza 20.</p>
      <p>Werdykt jest dolną medianą uporządkowanych ocen: „bez spinu”, „częściowy spin”, „spin”. Przy dwóch różnych środkowych ocenach wybierana jest łagodniejsza. Głosy „nie da się ocenić” nie wchodzą do tych median. Gdy wszystkie głosy są nierozstrzygnięte, wynik to „nie da się ocenić”; zapisane technicznie 0 nie świadczy wtedy o braku spinu.</p>
      <p>Starsze lub przygotowane poza Konsylium diagnozy mogą zawierać ocenę jednego modelu. Braku głosów Konsylium nie zastępujemy fikcyjną medianą.</p>
    </section>
    <section id="zgodnosc"><h2>Zgodność werdyktu i rozrzut</h2>
      <p>Zgodność to liczba modeli z werdyktem równym wynikowi diagnozy podzielona przez liczbę otrzymanych odpowiedzi. Odpowiedź „nie da się ocenić” pozostaje w mianowniku, a brak odpowiedzi jest pomijany. Rozrzut pokazuje najniższą i najwyższą liczbową ocenę uczestników.</p>
      <p>Modele mogą popełnić ten sam błąd, więc jednomyślność nie jest potwierdzeniem faktu. Docelowy skład to co najmniej 4 odpowiedzi z 3 firm i model polski; przy ograniczeniach usług możliwa jest diagnoza z 3 odpowiedzi i jawnym opisem braków. <Link href="/konsylium#sklad">Skład, role i oświadczenia</Link>.</p>
    </section>
    <section id="twierdzenia"><h2>Statusy twierdzeń</h2>
      <ul>
        <li><strong>Potwierdzone:</strong> znalezione źródła wspierają twierdzenie.</li>
        <li><strong>Sprzeczne ze źródłami:</strong> znalezione źródła przeczą twierdzeniu.</li>
        <li><strong>Wprowadzające w błąd:</strong> źródła wskazują istotne pominięcie, zniekształcenie lub nieuprawniony wniosek.</li>
        <li><strong>Niezweryfikowane / nie do sprawdzenia:</strong> brak wystarczającej weryfikacji, źródła albo możliwości rozstrzygnięcia.</li>
      </ul>
      <p>Status faktu wymaga źródła zwróconego przez wyszukiwanie. Bez niego wynik wraca do „niezweryfikowane”. Przed zliczaniem podobne twierdzenia są łączone na podstawie wspólnych słów. Przy różnych sprawdzonych ocenach w jednej grupie mechanizm zachowuje kolejno „sprzeczne ze źródłami”, „wprowadzające w błąd”, potem „potwierdzone” i scala źródła. To reguła zliczania, nie dodatkowy werdykt o prawdzie.</p>
      <p>W zestawieniach „opinie” jest nazwą grupy niezweryfikowanych twierdzeń bez źródeł. Obecny mechanizm nie rozróżnia w tej grupie opinii od faktu, którego nie udało się sprawdzić. Ta etykieta nie dowodzi, że wypowiedź jest z natury nieweryfikowalna. Dodanie źródła pomocniczego przez laboratorium samo nie zmienia statusu twierdzenia.</p>
    </section>
    <section id="techniki"><h2>21 kategorii technik i „Inne”</h2>
      <p>Rodziny porządkują kategorie. Jedna diagnoza może należeć do kilku rodzin i zawierać kilka kategorii, więc ich udziały nie muszą sumować się do 100%.</p>
      <dl className="sc-doc-definitions">
        <div><dt>Dane i wnioskowanie — 10 kategorii</dt><dd>Liczba bez punktu odniesienia; Wybiórcze dane; Pominięcie kontekstu; Przeinaczenie faktów; Teza bez dowodu; Fałszywa przyczynowość; Nadmierne uogólnienie; Fałszywa analogia i skojarzenie; Fałszywa alternatywa; Odwołanie do autorytetu.</dd></div>
        <div><dt>Emocje i przedstawienie — 6 kategorii</dt><dd>Apel do emocji; Straszenie; Przesada; Etykietowanie; My kontra oni; Sugestia i niedopowiedzenie.</dd></div>
        <div><dt>Spór i odpowiedzialność — 5 kategorii</dt><dd>Atak na osobę; Przypisywanie intencji; Słomiany człowiek (w interfejsie: Zniekształcenie cudzego stanowiska); Zmiana tematu; Przypisywanie sobie zasług.</dd></div>
        <div><dt>Inne</dt><dd>Kategoria na techniki, których nie obejmuje pozostały słownik.</dd></div>
      </dl>
      <p>Do wspólnej diagnozy trafia technika z cytatem obecnym w materiale. Przy co najmniej 3 rozstrzygniętych głosach musi ją wskazać co najmniej 2 członków. Gdy tylko 1–2 głosy rozstrzygają ocenę, wystarcza jedno wskazanie; pozostali uczestnicy mogą odpowiedzieć „nie da się ocenić”. Proces wybiera najwyżej 6 technik. W statystykach jedna kategoria jest liczona najwyżej raz na diagnozę.</p>
    </section>
    <section id="slowa"><h2>Słowa nacechowane</h2>
      <p>Rozpoznajemy pięć grup: strach i zagrożenie, gniew i oburzenie, pogarda i wyśmiewanie, duma i wspólnota oraz współczucie i krzywda. Najpierw wykorzystujemy zweryfikowane wskazania modeli: słowo lub zwrot musi wystąpić we wpisie. Gdy ich brakuje, działa polski słownik z wyjątkami kontekstowymi.</p>
      <p>Powtórzenia tego samego zapisu są scalane bez rozróżniania wielkości liter. Licznik dotyczy rozpoznanych różnych słów lub zwrotów, nie wszystkich wystąpień i nie odsetka tekstu. Lista pokazuje najwyżej 8 przykładów; przy metodzie słownikowej licznik może obejmować więcej. Nacechowane słowo samo w sobie nie przesądza o spinie.</p>
    </section>
    <section id="wykresy"><h2>Mianowniki wykresów i próg próby</h2>
      <p>Publiczne agregaty obejmują opublikowane, nieukryte diagnozy dostępnych wpisów. Główne porównania dotyczą 30 dni według daty diagnozy, w strefie czasowej serwisu. Liczniki łączne i lejek obejmują całą historię; kolejka jest jej aktualnym stanem. Lejek nie śledzi jednej zamkniętej grupy wpisów przez wszystkie etapy.</p>
      <ul>
        <li><strong>Werdykty, średnia i rozkład siły:</strong> mianownikiem jest liczba diagnoz w danej grupie i okresie. Średnia na wykresie to średnia arytmetyczna wyników diagnoz, choć wynik pojedynczego Konsylium pochodzi z mediany. Obecny agregat uwzględnia także zapisane wartości diagnoz nierozstrzygniętych.</li>
        <li><strong>Techniki i rodziny:</strong> liczba diagnoz zawierających kategorię lub rodzinę. Udział odnosi się do wszystkich diagnoz danej grupy, nie do sumy technik. Rodzina występująca kilka razy w jednej diagnozie liczy się raz.</li>
        <li><strong>Twierdzenia:</strong> podstawą są odrębne twierdzenia po scaleniu powtórzeń w obrębie diagnozy. Udziały ocen faktów odnoszą się do twierdzeń sprawdzonych i popartych źródłami; grupa niezweryfikowana jest liczona osobno.</li>
        <li><strong>Słowa nacechowane:</strong> średnia liczba rozpoznanych słów lub zwrotów na diagnozę w grupie. Nie jest to udział w liczbie wszystkich słów.</li>
        <li><strong>Jednomyślność Konsylium:</strong> odsetek diagnoz ze zgodnymi wszystkimi głosami wśród diagnoz z co najmniej 2 odpowiedziami, nie wszystkich analiz.</li>
        <li><strong>Polubienia:</strong> średnia dla wpisów z dostępną nieujemną liczbą polubień, osobno dla werdyktów. Brak danych o reakcjach nie jest zerem; popularność nie jest dowodem prawdziwości.</li>
      </ul>
      <p>Próg wystarczającej próby wynosi <strong>10 obserwacji</strong> w odpowiednim liczniku lub grupie. Poniżej progu dane otrzymują oznaczenie małej próby. To sygnał ograniczenia, nie test istotności statystycznej ani gwarancja reprezentatywności po osiągnięciu 10.</p>
    </section>
    <section id="ograniczenia"><h2>Ograniczenia</h2>
      <p>AI może pomylić cytat, kontekst, ironię, ocenę faktu lub kategorię techniki. Modele różnych firm mogą dzielić dane treningowe i uprzedzenia. Wyszukiwanie nie obejmuje całej wiedzy, a źródła mogą być nieaktualne lub niedostępne. Limity usług zmieniają skład i zakres badań.</p>
      <p>Przypisanie obozu odzwierciedla zapis przy pobraniu wpisu. Zestawienia partii korzystają z danych rejestru osób, które mogą się zmieniać. Wnioski dotyczą tej próby komunikatów; nie tworzymy zbiorczej oceny prawdomówności osoby.</p>
    </section>
    <section id="korekty"><h2>Błędy, wycofanie i odpowiedź</h2>
      <p>Wyślij trwały link do diagnozy, opis problemu i źródła na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Autor wypowiedzi może tą samą drogą przedstawić odpowiedź.</p>
      <p>Obecnie operator może wycofać lub ukryć całą diagnozę. Zapisywane są data i powód ukrycia; treści, werdyktu ani siły nie edytuje się ręcznie. Ukryta diagnoza znika z publicznych wyników. Korekta językowa i poprawka po recenzji AI zachodzą przed publikacją.</p>
      <p>Publiczny, datowany rejestr zmian i odpowiedzi pod diagnozą jest planowany. Nie deklarujemy dziś dostępnej historii korekt ani automatycznej ponownej analizy każdego zgłoszenia. <Link href="/konsylium/karta">Karta Konsylium</Link> rozróżnia tę zasadę docelową od obecnych możliwości.</p>
    </section>
  </DocLayout>;
}
