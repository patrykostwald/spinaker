import Link from "next/link";
import { CouncilRecruitmentLog, CouncilRoster, HowItWorksFilm } from "@spin-clinic/ui";
import { DocLayout } from "@spin-clinic/ui/kit";

export const metadata = {
  title: "Konsylium AI — spin.clinic",
  description: "Jak kilka modeli AI różnych firm wspólnie stawia diagnozę: droga wpisu, role, skład, łączenie głosów, narzędzia i zasady.",
  alternates: { canonical: "/konsylium" },
};

const sections = [
  { id: "film", label: "Film" },
  { id: "droga", label: "Droga wpisu" },
  { id: "role", label: "Kto co robi" },
  { id: "glosy", label: "Jak łączymy głosy" },
  { id: "sklad", label: "Aktualny skład" },
  { id: "narzedzia", label: "Narzędzia" },
  { id: "granice", label: "Granice analizy" },
  { id: "zasady", label: "Zasady i błędy" },
];

/** Kolejność jak w kodzie: clinic_council.diagnose (głosy → łączenie → fakty → laboratorium → uzasadnienie → recenzja → język). */
const FLOW = [
  ["Selekcja", "Strażnik czyta nowe wpisy polityków i wybiera te, w których jest teza do sprawdzenia."],
  ["Niezależne głosy", "Kilka modeli różnych firm ocenia wpis osobno. Żaden nie widzi odpowiedzi innych."],
  ["Łączenie", "Stałe reguły łączą głosy w jeden werdykt, siłę spinu i listę technik."],
  ["Źródła i badania", "Twierdzenia trafiają do wyszukiwarki, a laboratorium dodaje badania pomocnicze. Źródło musi pochodzić z wyników."],
  ["Uzasadnienie", "Przewodniczący pisze diagnozę z ustaleń, recenzent sprawdza zgodność, językoznawca poprawia polszczyznę."],
  ["Publikacja", "Diagnoza ukazuje się automatycznie, z głosami modeli i ograniczeniami. Nikt nie edytuje jej treści. Wybrane wyniki trafiają też jako skróty i filmy do mediów społecznościowych — zawsze z linkiem do pełnej analizy."],
];

const ROLES = [
  { role: "Członkowie Konsylium", who: "gpt-oss · Qwen · Nemotron · Gemini · Bielik · PLLuM · Llama · Mistral",
    text: "Każdy osobno podaje werdykt, siłę 0–100, techniki z dosłownym cytatem i twierdzenia do sprawdzenia." },
  { role: "Sprawdzanie faktów", who: "Gemini z wyszukiwarką Google",
    text: "Szuka źródeł do każdego twierdzenia. Bez źródła twierdzenie zostaje niezweryfikowane." },
  { role: "Konsultant", who: "Claude (Anthropic) · płatny",
    text: "Mocniejsze sprawdzenie faktów, gdy modele są podzielone (zgoda poniżej 2/3) albo spin jest silny (70/100 i więcej)." },
  { role: "Laboratorium", who: "HerBERT · Google Fact Check · GUS · Firecrawl",
    text: "Badania pomocnicze: wydźwięk, wcześniejsze fact-checki, dane GUS, obecność cytatu w źródle. Nie zmieniają werdyktu." },
  { role: "Przewodniczący", who: "Gemini (w zapasie inne modele)",
    text: "Pisze uzasadnienie wyłącznie z ocen Konsylium i dowodów. Nie może zmienić werdyktu, siły ani dodać techniki." },
  { role: "Recenzent", who: "Nemotron (w zapasie inne modele)",
    text: "Sprawdza, czy tekst zgadza się z ocenami i Kartą. Przy uwagach przewodniczący raz poprawia diagnozę; brak recenzji nie wstrzymuje publikacji." },
  { role: "Językoznawca", who: "Bielik (w zapasie PLLuM, Qwen, Gemini)",
    text: "Poprawia tylko polszczyznę. Gdy poprawka wyraźnie zmienia długość tekstu albo nie jest po polsku, zostaje wersja przewodniczącego." },
];

/** Przykład obliczenia (nie rzeczywista diagnoza) — zgodny z clinic_council.combine. */
const EXAMPLE = [
  { model: "Model A", verdict: "partial", label: "Częściowy spin", strength: 30 },
  { model: "Model B", verdict: "partial", label: "Częściowy spin", strength: 40 },
  { model: "Model C", verdict: "partial", label: "Częściowy spin", strength: 60 },
  { model: "Model D", verdict: "spin", label: "Spin", strength: 80 },
];

const TOOLS: Array<[string, string, "obsługiwane" | "planowane"]> = [
  ["Konsylium, łączenie głosów, przewodniczący, recenzent, językoznawca", "rdzeń każdej diagnozy", "obsługiwane"],
  ["Gemini z wyszukiwarką Google", "źródła do twierdzeń", "obsługiwane"],
  ["Claude z wyszukiwaniem", "konsultacja przy sporze i silnym spinie, gdy pozwala budżet", "obsługiwane"],
  ["Słownik słów nacechowanych i 21 kategorii technik", "wspólny język diagnoz", "obsługiwane"],
  ["HerBERT (Hugging Face)", "wydźwięk i mowa nienawiści — sygnał pomocniczy", "obsługiwane"],
  ["Google Fact Check Tools", "wcześniejsze sprawdzenia innych redakcji", "obsługiwane"],
  ["GUS BDL", "bezrobocie i wynagrodzenia w Polsce", "obsługiwane"],
  ["Firecrawl", "czy cytat naprawdę jest w źródle (do 3 na diagnozę)", "obsługiwane"],
  ["Wayback Machine", "publiczna kopia wpisu, w tle", "obsługiwane"],
  ["Własny detektor technik (XLM-RoBERTa)", "na własnej maszynie", "planowane"],
  ["Eurostat, NBP, rejestry prawa", "szersze sprawdzanie liczb i przepisów", "planowane"],
];

export default function CouncilPage() {
  return <DocLayout eyebrow="KONSYLIUM AI" title="Kilka modeli AI, jedna diagnoza" version="1.1" updatedAt="2026-09-29" sections={sections}
    lead="Wybrane wpisy polityków osobno ocenia kilka modeli AI różnych firm. Porównujemy ich głosy, szukamy źródeł i przygotowujemy wspólną diagnozę — z jawnym składem i ograniczeniami. Modele mogą się mylić.">

    <section aria-label="Film: jak działa spin.clinic"><HowItWorksFilm /></section>

    <section id="droga"><h2>Droga wpisu do diagnozy</h2>
      <ol className="sc-kons-flow">{FLOW.map(([title, text], index) =>
        <li key={title}><span className="sc-kons-flow__n">{index + 1}</span><strong>{title}</strong><p>{text}</p></li>)}</ol>
    </section>

    <section id="role"><h2>Kto co robi</h2>
      <p>Konsylium działa jak rada lekarska: kilku niezależnych specjalistów, osobne badania i jeden opis wyniku. Poniżej domyślna obsada ról — gdy model nie odpowie, zastępuje go kolejny. Rzeczywistych wykonawców pokazujemy przy każdej diagnozie.</p>
      <ul className="sc-kons-roles">{ROLES.map(item =>
        <li key={item.role}><h3>{item.role}</h3><p className="sc-kons-roles__who">{item.who}</p><p>{item.text}</p></li>)}</ul>
    </section>

    <section id="glosy"><h2>Jak łączymy głosy</h2>
      <div className="sc-kons-example" aria-label="Przykład obliczenia, nie rzeczywista diagnoza">
        <ul className="sc-kons-example__votes">{EXAMPLE.map(vote =>
          <li key={vote.model}><span className="sc-kons-example__model">{vote.model}</span><span className="sc-verdict" data-verdict={vote.verdict}>{vote.label}</span>
            <span className="sc-kons-example__track"><i style={{ width: `${vote.strength}%` }} /></span><b>{vote.strength}</b></li>)}</ul>
        <div className="sc-kons-example__result">
          <p className="sc-kons-example__lbl">Wynik</p>
          <span className="sc-verdict" data-verdict="partial">Częściowy spin</span>
          <p className="sc-kons-example__num">50<small>/100</small></p>
          <p className="sc-kons-example__agree"><strong>3/4</strong> ten sam werdykt · rozrzut 30–80</p>
        </div>
      </div>
      <p className="sc-kons-example__cap">Przykład obliczenia, nie rzeczywista diagnoza.</p>
      <ul className="sc-kons-rules">
        <li><strong>Werdykt i siła</strong> to środkowe oceny (mediana). Jeden skrajny model nie przesądza wyniku; przy remisie wybieramy łagodniejszą ocenę.</li>
        <li><strong>Technika</strong> wymaga dosłownego cytatu z badanego materiału. Przy co najmniej trzech rozstrzygniętych głosach muszą ją wskazać minimum dwa modele; przy jednym lub dwóch takich głosach wystarczy jedno wskazanie.</li>
        <li><strong>Zgoda modeli</strong> to informacja dla czytelnika, nie dowód prawdy: modele mogą popełnić ten sam błąd.</li>
      </ul>
    </section>

    <section id="sklad"><h2>Aktualny skład</h2>
      <ul className="sc-kons-rulebar">
        <li><strong>4</strong><span>odpowiedzi — cel dla każdego wpisu</span></li>
        <li><strong>3+</strong><span>różne firmy</span></li>
        <li><strong>PL</strong><span>model polski wybierany jako pierwszy</span></li>
      </ul>
      <p>Do każdego wpisu dobieramy modele różnych firm, zaczynając od polskiego. Gdy któryś nie odpowie, dołącza kolejny. Przy mniej niż 3 odpowiedziach diagnoza się nie ukazuje; niepełny skład opisujemy w jej ograniczeniach. Poniżej modele skonfigurowane do pracy w Konsylium.</p>
      <CouncilRoster />
    </section>

    <section id="rekrutacja"><h2>Rekrutacja do Konsylium</h2>
      <p>Skład nie jest zamknięty. Co noc Rekruter Konsylium przegląda katalogi darmowych modeli i wybiera najwyżej jednego kandydata — pierwszeństwo ma model polski i firma, której jeszcze nie ma w składzie. Kandydat zdaje egzamin: ocenia te same wpisy polityków co Konsylium. Liczy się zgodność werdyktu i siły spinu z diagnozą końcową, cytowanie technik i polszczyzna. Obecni członkowie głosują, a przyjęty model musi przyjąć Kartę; role dostaje tylko wtedy, gdy wynik egzaminu je uzasadnia.</p>
      <p>Członek, który od trzech dni nie odpowiada (np. zniknął u dostawcy), zostaje zawieszony i wraca sam, gdy znów zacznie działać. Wszystkie decyzje zapisujemy poniżej. Do 7 października Rekruter działa w trybie próbnym: przyjęcia są rekomendacjami.</p>
      <CouncilRecruitmentLog />
    </section>

    <section id="narzedzia"><h2>Narzędzia</h2>
      <table className="sc-method-table sc-kons-tools"><thead><tr><th>Narzędzie</th><th>Do czego</th><th>W systemie</th></tr></thead>
        <tbody>{TOOLS.map(([name, use, state]) =>
          <tr key={name}><th scope="row">{name}</th><td>{use}</td><td><span className="sc-kons-state" data-state={state}>{state}</span></td></tr>)}</tbody></table>
      <p className="sc-method-note">Narzędzie obsługiwane przez system działa, gdy ma dostęp i wolny limit. Czy użyto go przy konkretnej diagnozie, widać w jej wynikach.</p>
    </section>

    <section id="granice"><h2>Granice analizy</h2>
      <ul className="sc-kons-limits">
        <li>Diagnoza wymaga co najmniej 3 odpowiedzi; skład bywa ograniczony, a część badań pominięta.</li>
        <li>Brak źródła oznacza brak weryfikacji, nie fałsz.</li>
        <li>Brak recenzji albo jej negatywny wynik nie wstrzymuje automatycznie publikacji.</li>
        <li>Film dołączony do wpisu nie jest analizowany; wywiady mają osobny proces.</li>
        <li>Zgoda modeli nie jest dowodem prawdy — mogą popełnić ten sam błąd.</li>
      </ul>
    </section>

    <section id="zasady"><h2>Zasady i błędy</h2>
      <ul className="sc-kons-links">
        <li><Link href="/konsylium/karta"><strong>Karta Konsylium</strong><span>12 zasad pracy i oświadczenia modeli</span></Link></li>
        <li><Link href="/metodologia"><strong>Metodologia</strong><span>selekcja, obliczenia i ograniczenia</span></Link></li>
        <li><a href="mailto:kontakt@spin.clinic"><strong>Zgłoś błąd</strong><span>link do diagnozy i źródła na kontakt@spin.clinic</span></a></li>
      </ul>
      <p>Operator może wycofać diagnozę z publicznego widoku, ale nie zmienia jej treści, werdyktu ani siły.</p>
    </section>
  </DocLayout>;
}
