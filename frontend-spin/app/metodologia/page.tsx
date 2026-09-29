import Link from "next/link";
import { DocLayout } from "@spin-clinic/ui/kit";

export const metadata = {
  title: "Metodologia — spin.clinic",
  description: "Jak wybieramy wpisy, łączymy oceny AI i liczymy dane Kliniki. Zakres, ograniczenia i zasady zgłaszania błędów.",
  alternates: { canonical: "/metodologia" },
};

const sections = [
  { id: "droga", label: "W skrócie" }, { id: "selekcja", label: "Selekcja wpisów" },
  { id: "zakres", label: "Zakres analizy" }, { id: "werdykty", label: "Werdykty i siła" },
  { id: "zgodnosc", label: "Zgodność modeli" }, { id: "twierdzenia", label: "Statusy twierdzeń" },
  { id: "techniki", label: "Rodziny technik" }, { id: "slowa", label: "Słowa nacechowane" },
  { id: "wykresy", label: "Jak liczymy dane" }, { id: "ograniczenia", label: "Ograniczenia" },
  { id: "korekty", label: "Błędy i wycofanie" },
];

const steps = [
  ["Selekcja", "Strażnik czyta nowe wpisy i wybiera te z tezą do sprawdzenia."],
  ["Konsylium", "Kilka modeli różnych firm osobno ocenia ten sam wpis."],
  ["Dowody", "Twierdzenia trafiają do wyszukiwarki; ocena faktu wymaga źródła."],
  ["Publikacja", "Diagnoza ukazuje się automatycznie. Człowiek może ją tylko wycofać."],
];

const verdicts = [
  ["spin", "Spin", "Wyraźne techniki perswazji lub manipulacyjne przedstawienie treści."],
  ["partial", "Częściowy spin", "Takie elementy są, ale nie określają całego komunikatu."],
  ["no_spin", "Bez spinu", "Brak istotnego spinu w badanym materiale. To nie certyfikat prawdy."],
  ["unclear", "Nie da się ocenić", "Dane nie pozwalają rozstrzygnąć oceny."],
];

const claims = [
  ["ok", "Potwierdzone", "źródła wspierają twierdzenie"],
  ["bad", "Sprzeczne ze źródłami", "źródła przeczą twierdzeniu"],
  ["mid", "Wprowadzające w błąd", "istotne pominięcie, zniekształcenie lub nieuprawniony wniosek"],
  ["unverified", "Niezweryfikowane", "brak źródła albo nie da się tego sprawdzić"],
];

const families = [
  ["dane", "Dane i wnioskowanie", ["Liczba bez punktu odniesienia", "Wybiórcze dane", "Pominięcie kontekstu", "Przeinaczenie faktów", "Teza bez dowodu", "Fałszywa przyczynowość", "Nadmierne uogólnienie", "Fałszywa analogia i skojarzenie", "Fałszywa alternatywa", "Odwołanie do autorytetu"]],
  ["przedstawienie", "Emocje i przedstawienie", ["Apel do emocji", "Straszenie", "Przesada", "Etykietowanie", "My kontra oni", "Sugestia i niedopowiedzenie"]],
  ["spor", "Spór i odpowiedzialność", ["Atak na osobę", "Przypisywanie intencji", "Zniekształcenie cudzego stanowiska", "Zmiana tematu", "Przypisywanie sobie zasług"]],
] as const;

const measures = [
  ["Werdykty i siła", "liczba diagnoz w grupie i okresie; średnia arytmetyczna wyników diagnoz"],
  ["Techniki i rodziny", "liczba diagnoz z daną kategorią (raz na diagnozę), nie suma technik"],
  ["Twierdzenia", "odrębne twierdzenia po scaleniu powtórzeń; niezweryfikowane osobno"],
  ["Słowa nacechowane", "średnia liczba różnych słów lub zwrotów na diagnozę"],
  ["Jednomyślność", "diagnozy z co najmniej 2 odpowiedziami, w których wszystkie głosy są zgodne"],
  ["Polubienia", "tylko wpisy z dostępną liczbą; brak danych to nie zero"],
];

export default function MethodologyPage() {
  return <DocLayout eyebrow="METODOLOGIA" title="Jak analizujemy przekaz" version="1.0" updatedAt="2026-09-29" sections={sections}
    lead="Diagnoza dotyczy konkretnego komunikatu, nie osoby. Poniżej: skąd biorą się wpisy, jak powstaje wynik i jak liczymy dane Kliniki.">

    <section id="droga"><h2>W skrócie</h2>
      <ol className="sc-method-steps">{steps.map(([title, text], index) =>
        <li key={title}><span className="sc-method-steps__n">{index + 1}</span><strong>{title}</strong><p>{text}</p></li>)}</ol>
    </section>

    <section id="selekcja"><h2>Selekcja wpisów</h2>
      <p>Czytamy wpisy z obserwowanych kont X polityków i partii z ostatnich 3 dni. Strażnik daje każdemu wstępny wynik — to nie jest siła spinu.</p>
      <figure className="sc-method-gauge" aria-label="Progi wyniku selekcji">
        <div className="sc-method-gauge__bar"><span style={{ flexBasis: "40%" }}>pomijany</span><span style={{ flexBasis: "35%" }}>do decyzji</span><span style={{ flexBasis: "25%" }}>kolejka automatyczna</span></div>
        <div className="sc-method-gauge__scale"><b>0</b><b style={{ left: "40%" }}>40</b><b style={{ left: "75%" }}>75</b><b>100</b></div>
      </figure>
      <p className="sc-method-note">To próba wybranych wypowiedzi, nie cała debata. Więcej diagnoz jednej strony nie znaczy, że ta strona częściej stosuje spin. Brak diagnozy nie oznacza „bez spinu”.</p>
    </section>

    <section id="zakres"><h2>Zakres analizy</h2>
      <div className="sc-method-pair">
        <div><h3>Badamy</h3><ul><li>tekst wpisu</li><li>zdjęcia i grafiki: opis i tekst na obrazie</li><li>tytuły i opisy podlinkowanych stron</li></ul></div>
        <div><h3>Nie badamy we wpisach</h3><ul><li>filmów dołączonych do wpisu</li><li>tego, czego model nie odczytał — opisujemy to w ograniczeniach diagnozy</li></ul></div>
      </div>
      <p><Link href="/klinika/wywiady">Wywiady</Link> mają osobny proces: transkrypcja i osobne oceny gościa oraz prowadzącego.</p>
    </section>

    <section id="werdykty"><h2>Werdykty i siła spinu</h2>
      <ul className="sc-method-verdicts">{verdicts.map(([key, label, text]) =>
        <li key={key}><span className="sc-verdict" data-verdict={key}>{label}</span><p>{text}</p></li>)}</ul>
      <figure className="sc-method-strength">
        <p className="sc-method-strength__num">55<small>/100</small></p>
        <div><div className="sc-method-strength__track"><i style={{ width: "55%" }} /></div>
          <figcaption>Siła spinu to nasilenie rozpoznanych zabiegów — nie procent fałszu ani winy. Wynik to mediana ocen modeli; dla „bez spinu” najwyżej 20.</figcaption></div>
      </figure>
      <p>Werdykt to środkowa ocena Konsylium; przy remisie wybieramy łagodniejszą. Głosy „nie da się ocenić” nie wchodzą do mediany. Nie dopisujemy fikcyjnych głosów tam, gdzie oceniał jeden model.</p>
    </section>

    <section id="zgodnosc"><h2>Zgodność modeli</h2>
      <div className="sc-method-agree">
        <p className="sc-method-agree__num">2/3<small>ten sam werdykt</small></p>
        <p>Tyle modeli dało werdykt równy wynikowi diagnozy. „Nie da się ocenić” liczy się do mianownika, brak odpowiedzi — nie. Obok pokazujemy rozrzut ocen siły.</p>
      </div>
      <p className="sc-method-note">Modele mogą popełnić ten sam błąd, więc zgoda nie jest dowodem. Docelowo: co najmniej 4 odpowiedzi z 3 firm i model polski; przy limitach usług — 3 odpowiedzi z opisem braków. <Link href="/konsylium#sklad">Aktualny skład</Link></p>
    </section>

    <section id="twierdzenia"><h2>Statusy twierdzeń</h2>
      <ul className="sc-method-claims">{claims.map(([key, label, text]) =>
        <li key={key}><i data-k={key} /><strong>{label}</strong><span>{text}</span></li>)}</ul>
      <p>Status faktu wymaga źródła z wyszukiwania — bez niego twierdzenie zostaje niezweryfikowane. Podobne twierdzenia łączymy przed liczeniem. W zestawieniach grupa „opinie” obejmuje dziś także fakty, których nie udało się sprawdzić.</p>
    </section>

    <section id="techniki"><h2>Rodziny technik</h2>
      <p>21 kategorii w trzech rodzinach oraz „Inne”. Technika trafia do diagnozy tylko z cytatem z materiału i gdy wskaże ją co najmniej 2 członków Konsylium (przy 1–2 rozstrzygniętych głosach wystarczy jedno wskazanie). Najwyżej 6 technik na diagnozę.</p>
      <div className="sc-method-families">{families.map(([key, label, items]) =>
        <div key={key} className="sc-method-family" data-family={key}>
          <h3><i />{label}<span>{items.length}</span></h3>
          <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>
        </div>)}</div>
    </section>

    <section id="slowa"><h2>Słowa nacechowane</h2>
      <ul className="sc-method-chips">{["strach i zagrożenie", "gniew i oburzenie", "pogarda i wyśmiewanie", "duma i wspólnota", "współczucie i krzywda"].map(item => <li key={item}>{item}</li>)}</ul>
      <p>Najpierw bierzemy wskazania modeli (słowo musi być we wpisie), a gdy ich brak — polski słownik. Liczymy różne słowa i zwroty, nie wszystkie wystąpienia. Samo nacechowane słowo nie przesądza o spinie.</p>
    </section>

    <section id="wykresy"><h2>Jak liczymy dane</h2>
      <p>Wykresy obejmują opublikowane, nieukryte diagnozy. Porównania dotyczą 30 dni według daty diagnozy.</p>
      <table className="sc-method-table"><thead><tr><th>Miara</th><th>Podstawa</th></tr></thead>
        <tbody>{measures.map(([name, base]) => <tr key={name}><th scope="row">{name}</th><td>{base}</td></tr>)}</tbody></table>
      <p className="sc-method-note">Poniżej <strong>10 obserwacji</strong> oznaczamy małą próbę. To sygnał ostrożności, nie test statystyczny.</p>
    </section>

    <section id="ograniczenia"><h2>Ograniczenia</h2>
      <ul>
        <li>AI może pomylić cytat, kontekst, ironię, ocenę faktu albo kategorię techniki.</li>
        <li>Modele różnych firm mogą mieć wspólne dane treningowe i uprzedzenia.</li>
        <li>Wyszukiwanie nie obejmuje całej wiedzy; źródła bywają nieaktualne.</li>
        <li>Limity usług zmieniają skład Konsylium i zakres badań.</li>
        <li>Wnioski dotyczą tej próby komunikatów — nie oceniamy prawdomówności osób.</li>
      </ul>
    </section>

    <section id="korekty"><h2>Błędy i wycofanie</h2>
      <div className="sc-method-callout">
        <p><strong>Widzisz błąd?</strong> Wyślij link do diagnozy, opis i źródła na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Tą samą drogą autor wypowiedzi może przesłać odpowiedź.</p>
      </div>
      <p>Operator może wycofać całą diagnozę — zapisujemy datę i powód. Treści, werdyktu ani siły nie poprawia się ręcznie. Publiczny rejestr korekt i odpowiedzi jest planowany. <Link href="/konsylium/karta">Karta Konsylium</Link></p>
    </section>
  </DocLayout>;
}
