import { DocumentLink as Link, documentTranslator, type DocumentLanguage } from "./locale";
import { CouncilRecruitmentLog, CouncilRoster, HowItWorksFilm } from "@spin-clinic/ui";
import { DocLayout } from "@spin-clinic/ui/kit";
import type { CSSProperties } from "react";

export function CouncilDocument({ lang = "pl" }: { lang?: DocumentLanguage }) {
  const t = documentTranslator(lang);
  const sections = [
    { id: "film", label: "Film" },
    { id: "droga", label: t("Droga wpisu") },
    { id: "role", label: t("Kto co robi") },
    { id: "glosy", label: t("Jak łączymy głosy") },
    { id: "sklad", label: t("Aktualny skład") },
    { id: "narzedzia", label: t("Narzędzia") },
    { id: "granice", label: t("Granice analizy") },
    { id: "zasady", label: t("Zasady i błędy") },
  ];

  /** Kolejność jak w kodzie: clinic_council.diagnose (głosy → łączenie → fakty → laboratorium → uzasadnienie → recenzja → język). */
  const FLOW = [
    [t("Selekcja"), t("Strażnik czyta nowe wpisy polityków i wybiera te, w których jest teza do sprawdzenia.")],
    [t("Niezależne głosy"), t("Kilka modeli różnych firm ocenia wpis osobno. Żaden nie widzi odpowiedzi innych.")],
    [t("Łączenie"), t("Stałe reguły łączą głosy w jeden werdykt, siłę spinu i listę technik.")],
    [t("Źródła i badania"), t("Twierdzenia trafiają do wyszukiwarki, a laboratorium dodaje badania pomocnicze. Źródło musi pochodzić z wyników.")],
    [t("Uzasadnienie"), t("Przewodniczący pisze diagnozę z ustaleń, recenzent sprawdza zgodność, językoznawca poprawia polszczyznę.")],
    [t("Publikacja"), t("Diagnoza ukazuje się automatycznie, z głosami modeli i ograniczeniami. Nikt nie edytuje jej treści. Wybrane wyniki trafiają też jako skróty i filmy do mediów społecznościowych - zawsze z linkiem do pełnej analizy.")],
  ];

  const ROLES = [
    { role: t("Członkowie Konsylium"), who: "gpt-oss · Qwen · Nemotron · Gemini · Bielik · PLLuM · Llama · Mistral",
      text: t("Każdy osobno podaje werdykt, siłę 0-100, techniki z dosłownym cytatem i twierdzenia do sprawdzenia.") },
    { role: t("Sprawdzanie faktów"), who: t("Gemini z wyszukiwarką Google"),
      text: t("Szuka źródeł do każdego twierdzenia. Bez źródła twierdzenie zostaje niezweryfikowane.") },
    { role: t("Konsultant"), who: t("Claude (Anthropic) · płatny"),
      text: t("Mocniejsze sprawdzenie faktów, gdy modele są podzielone (zgoda poniżej 2/3) albo spin jest silny (70/100 i więcej).") },
    { role: t("Laboratorium"), who: "HerBERT · Google Fact Check · GUS · Firecrawl",
      text: t("Badania pomocnicze: wydźwięk, wcześniejsze fact-checki, dane GUS, obecność cytatu w źródle. Nie zmieniają werdyktu.") },
    { role: t("Przewodniczący"), who: t("Gemini (w zapasie inne modele)"),
      text: t("Pisze uzasadnienie wyłącznie z ocen Konsylium i dowodów. Nie może zmienić werdyktu, siły ani dodać techniki.") },
    { role: t("Recenzent"), who: t("Nemotron (w zapasie inne modele)"),
      text: t("Sprawdza, czy tekst zgadza się z ocenami i Kartą. Przy uwagach przewodniczący raz poprawia diagnozę; brak recenzji nie wstrzymuje publikacji.") },
    { role: t("Językoznawca"), who: t("Bielik (w zapasie PLLuM, Qwen, Gemini)"),
      text: t("Poprawia tylko polszczyznę. Gdy poprawka wyraźnie zmienia długość tekstu albo nie jest po polsku, zostaje wersja przewodniczącego.") },
  ];

  /** Przykład obliczenia (nie rzeczywista diagnoza) - zgodny z clinic_council.combine. */
  const EXAMPLE = [
    { model: "Model A", verdict: "partial", label: t("Częściowy spin"), strength: 30 },
    { model: "Model B", verdict: "partial", label: t("Częściowy spin"), strength: 40 },
    { model: "Model C", verdict: "partial", label: t("Częściowy spin"), strength: 60 },
    { model: "Model D", verdict: "spin", label: "Spin", strength: 80 },
  ];

  const TOOLS: Array<[string, string, "obsługiwane" | "planowane"]> = [
    [t("Konsylium, łączenie głosów, przewodniczący, recenzent, językoznawca"), t("rdzeń każdej diagnozy"), "obsługiwane"],
    [t("Gemini z wyszukiwarką Google"), t("źródła do twierdzeń"), "obsługiwane"],
    [t("Claude z wyszukiwaniem"), t("konsultacja przy sporze i silnym spinie, gdy pozwala budżet"), "obsługiwane"],
    [t("Słownik słów nacechowanych i 21 kategorii technik"), t("wspólny język diagnoz"), "obsługiwane"],
    ["HerBERT (Hugging Face)", t("wydźwięk i mowa nienawiści - sygnał pomocniczy"), "obsługiwane"],
    ["Google Fact Check Tools", t("wcześniejsze sprawdzenia innych redakcji"), "obsługiwane"],
    ["GUS BDL", t("bezrobocie i wynagrodzenia w Polsce"), "obsługiwane"],
    ["Firecrawl", t("czy cytat naprawdę jest w źródle (do 3 na diagnozę)"), "obsługiwane"],
    ["Wayback Machine", t("publiczna kopia wpisu, w tle"), "obsługiwane"],
    [t("Własny detektor technik (XLM-RoBERTa)"), t("na własnej maszynie"), "planowane"],
    [t("Eurostat, NBP, rejestry prawa"), t("szersze sprawdzanie liczb i przepisów"), "planowane"],
  ];

  return <DocLayout lang={lang} alternateHref={lang === "pl" ? "/en/council" : "/konsylium"} eyebrow={t("KONSYLIUM AI")} title={<>{t("Kilka modeli AI,")}<br />{t("jedna diagnoza")}</>} version="1.1" updatedAt="2026-09-29" sections={sections}
    lead={t("Wybrane wpisy polityków osobno ocenia kilka modeli AI różnych firm. Porównujemy ich głosy, szukamy źródeł i przygotowujemy wspólną diagnozę - z jawnym składem i ograniczeniami. Modele mogą się mylić.")}>
    <section aria-label={t("Film: jak działa spin.clinic")}><HowItWorksFilm lang={lang} /></section>


    <section id="droga"><h2>{t("Droga wpisu do diagnozy")}</h2>
      <ol className="sc-kons-flow">{FLOW.map(([title, text], index) =>
        <li key={title}><span className="sc-kons-flow__n">{index + 1}</span><strong>{title}</strong><p>{text}</p></li>)}</ol>
    </section>

    <section id="role"><h2>{t("Kto co robi")}</h2>
      <p>{t("Konsylium działa jak rada lekarska: kilku niezależnych specjalistów, osobne badania i jeden opis wyniku. Poniżej domyślna obsada ról - gdy model nie odpowie, zastępuje go kolejny. Rzeczywistych wykonawców pokazujemy przy każdej diagnozie.")}</p>
      <ul className="sc-kons-roles">{ROLES.map(item =>
        <li key={item.role}><h3>{item.role}</h3><p className="sc-kons-roles__who">{item.who}</p><p>{item.text}</p></li>)}</ul>
    </section>

    <section id="glosy"><h2>{t("Jak łączymy głosy")}</h2>
      <div className="sc-kons-example" aria-label={t("Przykład obliczenia, nie rzeczywista diagnoza")}>
        <ul className="sc-kons-example__votes">{EXAMPLE.map(vote =>
          <li key={vote.model}><span className="sc-kons-example__model">{vote.model}</span><span className="sc-verdict" data-verdict={vote.verdict}>{vote.label}</span>
            <b>{vote.strength}</b></li>)}</ul>
        <div className="sc-kons-example__result">
          <p className="sc-kons-example__lbl">{t("Wynik")}</p>
          <span className="sc-verdict" data-verdict="partial">{t("Częściowy spin")}</span>
          <p className="sc-kons-example__num"><span className="sc-spin-num" style={{ "--spin": 50 } as CSSProperties}>50</span><small>/100</small></p>
          <p className="sc-kons-example__agree"><strong>3/4</strong> {t("ten sam werdykt · rozrzut od 30 do 80")}</p>
        </div>
      </div>
      <p className="sc-kons-example__cap">{t("Przykład obliczenia, nie rzeczywista diagnoza.")}</p>
      <ul className="sc-kons-rules">
        <li><strong>{t("Werdykt i siła")}</strong> {t("to środkowe oceny (mediana). Jeden skrajny model nie przesądza wyniku; przy remisie wybieramy łagodniejszą ocenę.")}</li>
        <li><strong>{t("Technika")}</strong> {t("wymaga dosłownego cytatu z badanego materiału. Przy co najmniej trzech rozstrzygniętych głosach muszą ją wskazać minimum dwa modele; przy jednym lub dwóch takich głosach wystarczy jedno wskazanie.")}</li>
        <li><strong>{t("Zgoda modeli")}</strong> {t("to informacja dla czytelnika, nie dowód prawdy: modele mogą popełnić ten sam błąd.")}</li>
      </ul>
    </section>

    <section id="sklad"><h2>{t("Aktualny skład")}</h2>
      <ul className="sc-kons-rulebar">
        <li><strong>4</strong><span>{t("odpowiedzi - cel dla każdego wpisu")}</span></li>
        <li><strong>3+</strong><span>{t("różne firmy")}</span></li>
        <li><strong>PL</strong><span>{t("model polski wybierany jako pierwszy")}</span></li>
      </ul>
      <p>{t("Do każdego wpisu dobieramy modele różnych firm, zaczynając od polskiego. Gdy któryś nie odpowie, dołącza kolejny. Przy mniej niż 3 odpowiedziach diagnoza się nie ukazuje; niepełny skład opisujemy w jej ograniczeniach. Poniżej modele skonfigurowane do pracy w Konsylium.")}</p>
      <CouncilRoster lang={lang} />
    </section>

    <section id="rekrutacja"><h2>{t("Rekrutacja do Konsylium")}</h2>
      <p>{t("Skład nie jest zamknięty. Co noc Rekruter Konsylium przegląda katalogi darmowych modeli i wybiera najwyżej jednego kandydata - pierwszeństwo ma model polski i firma, której jeszcze nie ma w składzie. Kandydat zdaje egzamin: ocenia te same wpisy polityków co Konsylium. Liczy się zgodność werdyktu i siły spinu z diagnozą końcową, cytowanie technik i polszczyzna. Obecni członkowie głosują, a przyjęty model musi przyjąć Kartę; role dostaje tylko wtedy, gdy wynik egzaminu je uzasadnia.")}</p>
      <p>{t("Członek, który od trzech dni nie odpowiada (np. zniknął u dostawcy), zostaje zawieszony i wraca sam, gdy znów zacznie działać. Wszystkie decyzje zapisujemy poniżej. Do 7 października Rekruter działa w trybie próbnym: przyjęcia są rekomendacjami.")}</p>
      <CouncilRecruitmentLog lang={lang} />
    </section>

    <section id="narzedzia"><h2>{t("Narzędzia")}</h2>
      <table className="sc-method-table sc-kons-tools"><thead><tr><th>{t("Narzędzie")}</th><th>{t("Do czego")}</th><th>{t("W systemie")}</th></tr></thead>
        <tbody>{TOOLS.map(([name, use, state]) =>
          <tr key={name}><th scope="row">{name}</th><td>{use}</td><td><span className="sc-kons-state" data-state={state}>{t(state)}</span></td></tr>)}</tbody></table>
      <p className="sc-method-note">{t("Narzędzie obsługiwane przez system działa, gdy ma dostęp i wolny limit. Czy użyto go przy konkretnej diagnozie, widać w jej wynikach.")}</p>
    </section>

    <section id="granice"><h2>{t("Granice analizy")}</h2>
      <ul className="sc-kons-limits">
        <li>{t("Diagnoza wymaga co najmniej 3 odpowiedzi; skład bywa ograniczony, a część badań pominięta.")}</li>
        <li>{t("Brak źródła oznacza brak weryfikacji, nie fałsz.")}</li>
        <li>{t("Brak recenzji albo jej negatywny wynik nie wstrzymuje automatycznie publikacji.")}</li>
        <li>{t("Film dołączony do wpisu nie jest analizowany; wywiady mają osobny proces.")}</li>
        <li>{t("Zgoda modeli nie jest dowodem prawdy - mogą popełnić ten sam błąd.")}</li>
      </ul>
    </section>

    <section id="zasady"><h2>{t("Zasady i błędy")}</h2>
      <ul className="sc-kons-links">
        <li><Link lang={lang} href="/konsylium/karta"><strong>{t("Karta Konsylium")}</strong><span>{t("12 zasad pracy i oświadczenia modeli")}</span></Link></li>
        <li><Link lang={lang} href="/metodologia"><strong>{t("Metodologia")}</strong><span>{t("selekcja, obliczenia i ograniczenia")}</span></Link></li>
        <li><a href="mailto:kontakt@spin.clinic"><strong>{t("Zgłoś błąd")}</strong><span>{t("link do diagnozy i źródła na kontakt@spin.clinic")}</span></a></li>
      </ul>
      <p>{t("Operator może wycofać diagnozę z publicznego widoku, ale nie zmienia jej treści, werdyktu ani siły.")}</p>
    </section>
  </DocLayout>;
}
