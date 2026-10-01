import { DocumentLink as Link, documentTranslator, type DocumentLanguage } from "./locale";
import { DocLayout } from "@spin-clinic/ui/kit";
import { SEMEVAL_MAP, SEMEVAL_UNRECOGNIZED } from "@spin-clinic/ui";
import { english } from "./english";

export function MethodologyDocument({ lang = "pl" }: { lang?: DocumentLanguage }) {
  const t = documentTranslator(lang);
  // nazwy kategorii z katalogu technik; brakujące w słowniku zostają po polsku
  const category = (name: string) => lang === "en" ? (english as Record<string, string>)[name] ?? name : name;
  const sections = [
    { id: "droga", label: t("W skrócie") }, { id: "selekcja", label: t("Selekcja wpisów") },
    { id: "zakres", label: t("Zakres analizy") }, { id: "werdykty", label: t("Werdykty i siła") },
    { id: "zgodnosc", label: t("Zgodność modeli") }, { id: "twierdzenia", label: t("Statusy twierdzeń") },
    { id: "techniki", label: t("Rodziny technik") }, { id: "slowa", label: t("Słowa nacechowane") },
    { id: "wykresy", label: t("Jak liczymy dane") }, { id: "ograniczenia", label: t("Ograniczenia") },
    { id: "korekty", label: t("Błędy i wycofanie") },
  ];

  const steps = [
    [t("Selekcja"), t("Strażnik czyta nowe wpisy i wybiera te z tezą do sprawdzenia.")],
    [t("Konsylium"), t("Kilka modeli różnych firm osobno ocenia ten sam wpis.")],
    [t("Dowody"), t("Twierdzenia trafiają do wyszukiwarki; ocena faktu wymaga źródła.")],
    [t("Publikacja"), t("Diagnoza ukazuje się automatycznie. Człowiek może ją tylko wycofać.")],
  ];

  const verdicts = [
    ["spin", "Spin", t("Wyraźne techniki perswazji lub manipulacyjne przedstawienie treści.")],
    ["partial", t("Częściowy spin"), t("Takie elementy są, ale nie określają całego komunikatu.")],
    ["no_spin", t("Bez spinu"), t("Brak istotnego spinu w badanym materiale. To nie certyfikat prawdy.")],
    ["unclear", t("Nie da się ocenić"), t("Dane nie pozwalają rozstrzygnąć oceny.")],
  ];

  const claims = [
    ["ok", t("Potwierdzone"), t("źródła wspierają twierdzenie")],
    ["bad", t("Sprzeczne ze źródłami"), t("źródła przeczą twierdzeniu")],
    ["mid", t("Wprowadzające w błąd"), t("istotne pominięcie, zniekształcenie lub nieuprawniony wniosek")],
    ["unverified", t("Niezweryfikowane"), t("brak źródła albo nie da się tego sprawdzić")],
  ];

  const families = [
    ["dane", t("Dane i wnioskowanie"), [t("Liczba bez punktu odniesienia"), t("Wybiórcze dane"), t("Pominięcie kontekstu"), t("Przeinaczenie faktów"), t("Teza bez dowodu"), t("Fałszywa przyczynowość"), t("Nadmierne uogólnienie"), t("Fałszywa analogia i skojarzenie"), t("Fałszywa alternatywa"), t("Odwołanie do autorytetu")]],
    ["przedstawienie", t("Emocje i przedstawienie"), [t("Apel do emocji"), t("Straszenie"), t("Przesada"), t("Etykietowanie"), t("My kontra oni"), t("Sugestia i niedopowiedzenie")]],
    ["spor", t("Spór i odpowiedzialność"), [t("Atak na osobę"), t("Przypisywanie intencji"), t("Zniekształcenie cudzego stanowiska"), t("Zmiana tematu"), t("Przypisywanie sobie zasług")]],
  ] as const;

  const measures = [
    [t("Werdykty i siła"), t("liczba diagnoz w grupie i okresie; średnia arytmetyczna wyników diagnoz")],
    [t("Techniki i rodziny"), t("liczba diagnoz z daną kategorią (raz na diagnozę), nie suma technik")],
    [t("Twierdzenia"), t("odrębne twierdzenia po scaleniu powtórzeń; niezweryfikowane osobno")],
    [t("Słowa nacechowane"), t("średnia liczba różnych słów lub zwrotów na diagnozę")],
    [t("Jednomyślność"), t("diagnozy z co najmniej 2 odpowiedziami, w których wszystkie głosy są zgodne")],
    [t("Polubienia"), t("tylko wpisy z dostępną liczbą; brak danych to nie zero")],
  ];

  return <DocLayout lang={lang} alternateHref={lang === "pl" ? "/en/methodology" : "/metodologia"} eyebrow={t("METODOLOGIA")} title={t("Jak analizujemy przekaz")} version="1.0" updatedAt="2026-10-01" sections={sections}
    lead={t("Diagnoza dotyczy konkretnego komunikatu, nie osoby. Poniżej: skąd biorą się wpisy, jak powstaje wynik i jak liczymy dane Kliniki.")}>

    <section id="droga"><h2>{t("W skrócie")}</h2>
      <ol className="sc-method-steps">{steps.map(([title, text], index) =>
        <li key={title}><span className="sc-method-steps__n">{index + 1}</span><strong>{title}</strong><p>{text}</p></li>)}</ol>
    </section>

    <section id="selekcja"><h2>{t("Selekcja wpisów")}</h2>
      <p>{t("Czytamy wpisy z obserwowanych kont X polityków i partii z ostatnich 3 dni. Strażnik daje każdemu wstępny wynik — to nie jest siła spinu.")}</p>
      <figure className="sc-method-gauge" aria-label={t("Progi wyniku selekcji")}>
        <div className="sc-method-gauge__bar"><span style={{ flexBasis: "40%" }}>{t("pomijany")}</span><span style={{ flexBasis: "35%" }}>{t("do decyzji")}</span><span style={{ flexBasis: "25%" }}>{t("kolejka automatyczna")}</span></div>
        <div className="sc-method-gauge__scale"><b>0</b><b style={{ left: "40%" }}>40</b><b style={{ left: "75%" }}>75</b><b>100</b></div>
      </figure>
      <p className="sc-method-note">{t("To próba wybranych wypowiedzi, nie cała debata. Więcej diagnoz jednej strony nie znaczy, że ta strona częściej stosuje spin. Brak diagnozy nie oznacza „bez spinu”.")}</p>
    </section>

    <section id="zakres"><h2>{t("Zakres analizy")}</h2>
      <div className="sc-method-pair">
        <div><h3>{t("Badamy")}</h3><ul><li>{t("tekst wpisu")}</li><li>{t("zdjęcia i grafiki: opis i tekst na obrazie")}</li><li>{t("tytuły i opisy podlinkowanych stron")}</li></ul></div>
        <div><h3>{t("Nie badamy we wpisach")}</h3><ul><li>{t("filmów dołączonych do wpisu")}</li><li>{t("tego, czego model nie odczytał — opisujemy to w ograniczeniach diagnozy")}</li></ul></div>
      </div>
      <p><Link lang={lang} href="/klinika/wywiady">{t("Wywiady")}</Link> {t("mają osobny proces: transkrypcja i osobne oceny gościa oraz prowadzącego.")}</p>
    </section>

    <section id="werdykty"><h2>{t("Werdykty i siła spinu")}</h2>
      <ul className="sc-method-verdicts">{verdicts.map(([key, label, text]) =>
        <li key={key}><span className="sc-verdict" data-verdict={key}>{label}</span><p>{text}</p></li>)}</ul>
      <figure className="sc-method-strength">
        <p className="sc-method-strength__num">55<small>/100</small></p>
        <div><div className="sc-method-strength__track"><i style={{ width: "55%" }} /></div>
          <figcaption>{t("Siła spinu to nasilenie rozpoznanych zabiegów — nie procent fałszu ani winy. Wynik to mediana ocen modeli; dla „bez spinu” najwyżej 20.")}</figcaption></div>
      </figure>
      <p>{t("Werdykt to środkowa ocena Konsylium; przy remisie wybieramy łagodniejszą. Głosy „nie da się ocenić” nie wchodzą do mediany. Nie dopisujemy fikcyjnych głosów tam, gdzie oceniał jeden model.")}</p>
    </section>

    <section id="zgodnosc"><h2>{t("Zgodność modeli")}</h2>
      <div className="sc-method-agree">
        <p className="sc-method-agree__num">2/3<small>{t("ten sam werdykt")}</small></p>
        <p>{t("Tyle modeli dało werdykt równy wynikowi diagnozy. „Nie da się ocenić” liczy się do mianownika, brak odpowiedzi — nie. Obok pokazujemy rozrzut ocen siły.")}</p>
      </div>
      <p className="sc-method-note">{t("Modele mogą popełnić ten sam błąd, więc zgoda nie jest dowodem. Docelowo: co najmniej 4 odpowiedzi z 3 firm i model polski; przy limitach usług — 3 odpowiedzi z opisem braków.")} <Link lang={lang} href="/konsylium#sklad">{t("Aktualny skład")}</Link></p>
    </section>

    <section id="twierdzenia"><h2>{t("Statusy twierdzeń")}</h2>
      <ul className="sc-method-claims">{claims.map(([key, label, text]) =>
        <li key={key}><i data-k={key} /><strong>{label}</strong><span>{text}</span></li>)}</ul>
      <p>{t("Status faktu wymaga źródła z wyszukiwania — bez niego twierdzenie zostaje niezweryfikowane. Podobne twierdzenia łączymy przed liczeniem. W zestawieniach grupa „opinie” obejmuje dziś także fakty, których nie udało się sprawdzić.")}</p>
    </section>

    <section id="techniki"><h2>{t("Rodziny technik")}</h2>
      <p>{t("21 kategorii w trzech rodzinach oraz „Inne”. Technika trafia do diagnozy tylko z cytatem z materiału i gdy wskaże ją co najmniej 2 członków Konsylium (przy 1–2 rozstrzygniętych głosach wystarczy jedno wskazanie). Najwyżej 6 technik na diagnozę.")}</p>
      <div className="sc-method-families">{families.map(([key, label, items]) =>
        <div key={key} className="sc-method-family" data-family={key}>
          <h3><i />{label}<span>{items.length}</span></h3>
          <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>
        </div>)}</div>
      <h3 id="semeval-title">{t("Zgodność z SemEval 2023")}</h3>
      <p><a href="https://propaganda.math.unipd.it/semeval2023task3/">SemEval 2023 Task 3</a> {t("to międzynarodowe zadanie badawcze, którego podzadanie 3 dotyczy rozpoznawania 23 technik perswazji w 6 grupach, także w tekstach po polsku. Poniższe przypisanie jest nasze i orientacyjne. Kategorie dotyczące rzetelności danych, faktów i wnioskowania wykraczają poza ten katalog perswazji językowej. Przypisanie nie oznacza walidacji skuteczności naszego systemu w SemEval.")}</p>
      <div className="sc-semeval-scroll" role="region" aria-labelledby="semeval-title" tabIndex={0}>
        <table className="sc-method-table sc-semeval-table"><thead><tr><th scope="col">{t("Nasza kategoria")}</th><th scope="col">{t("Odpowiednik SemEval")}</th></tr></thead>
          <tbody>{Object.entries(SEMEVAL_MAP).map(([name, equivalents]) => <tr key={name}><th scope="row">{category(name)}</th><td>{equivalents.length ? equivalents.join("; ") : <span className="sc-semeval-note">{t("brak odpowiednika")}</span>}</td></tr>)}
            <tr><th scope="row">{t("Słowa nacechowane (osobny moduł)")}</th><td>Loaded Language</td></tr>
          </tbody></table>
      </div>
      <p>{t("Techniki SemEval, których nie rozpoznajemy osobno:")}</p>
      <ul>{SEMEVAL_UNRECOGNIZED.map(name => <li key={name}>{name}</li>)}</ul>
    </section>

    <section id="slowa"><h2>{t("Słowa nacechowane")}</h2>
      <ul className="sc-method-chips">{[t("strach i zagrożenie"), t("gniew i oburzenie"), t("pogarda i wyśmiewanie"), t("duma i wspólnota"), t("współczucie i krzywda")].map(item => <li key={item}>{item}</li>)}</ul>
      <p>{t("Najpierw bierzemy wskazania modeli (słowo musi być we wpisie), a gdy ich brak — polski słownik. Liczymy różne słowa i zwroty, nie wszystkie wystąpienia. Samo nacechowane słowo nie przesądza o spinie.")}</p>
    </section>

    <section id="wykresy"><h2>{t("Jak liczymy dane")}</h2>
      <p>{t("Wykresy obejmują opublikowane, nieukryte diagnozy. Porównania dotyczą 30 dni według daty diagnozy.")}</p>
      <table className="sc-method-table"><thead><tr><th>{t("Miara")}</th><th>{t("Podstawa")}</th></tr></thead>
        <tbody>{measures.map(([name, base]) => <tr key={name}><th scope="row">{name}</th><td>{base}</td></tr>)}</tbody></table>
      <p className="sc-method-note">{t("Poniżej")} <strong>{t("10 obserwacji")}</strong> {t("oznaczamy małą próbę. To sygnał ostrożności, nie test statystyczny.")}</p>
    </section>

    <section id="ograniczenia"><h2>{t("Ograniczenia")}</h2>
      <ul>
        <li>{t("AI może pomylić cytat, kontekst, ironię, ocenę faktu albo kategorię techniki.")}</li>
        <li>{t("Modele różnych firm mogą mieć wspólne dane treningowe i uprzedzenia.")}</li>
        <li>{t("Wyszukiwanie nie obejmuje całej wiedzy; źródła bywają nieaktualne.")}</li>
        <li>{t("Limity usług zmieniają skład Konsylium i zakres badań.")}</li>
        <li>{t("Wnioski dotyczą tej próby komunikatów — nie oceniamy prawdomówności osób.")}</li>
      </ul>
    </section>

    <section id="korekty"><h2>{t("Błędy i wycofanie")}</h2>
      <div className="sc-method-callout">
        <p><strong>{t("Widzisz błąd?")}</strong> {t("Wyślij link do diagnozy, opis i źródła na")} <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>{t(". Tą samą drogą autor wypowiedzi może przesłać odpowiedź.")}</p>
      </div>
      <p>{t("Operator może wycofać całą diagnozę — zapisujemy datę i powód. Treści, werdyktu ani siły nie poprawia się ręcznie. Publiczny rejestr korekt i odpowiedzi jest planowany.")} <Link lang={lang} href="/konsylium/karta">{t("Karta Konsylium")}</Link></p>
    </section>
  </DocLayout>;
}
