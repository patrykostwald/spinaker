import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Jak działamy — spin.clinic",
  description: "Skąd bierzemy materiały, jak budujemy kontekst i dokąd zmierza spin.clinic.",
};

const stages = [
  {
    number: "01", label: "MVP", title: "Jedno miejsce dla wiadomości i ich historii",
    text: "Uruchamiamy stale aktualizowane archiwum polskich mediów. Każdy box prowadzi do oryginalnego materiału, a po otwarciu pokazuje powiązane publikacje i rozwój wydarzeń. Redakcja spin.clinic tworzy pierwsze nitki, a Dr Spin pomaga szybko sprawdzać publiczne wypowiedzi.",
    technology: "Supabase i PostgreSQL · harvestery RSS, API i stron publicznych · Next.js · wyszukiwanie pełnotekstowe i semantyczne · zewnętrzne modele AI jako narzędzia redakcyjne",
  },
  {
    number: "02", label: "SPOŁECZNOŚĆ", title: "Własny profil, własne źródła i wspólne nitki",
    text: "Dodajemy konta użytkowników, ulubione nitki, prywatną personalizację i alerty. Użytkownik może ocenić materiał, zostawić jeden krótki komentarz i zdecydować, co pokazuje na swoim profilu. Zweryfikowani dziennikarze i autorzy dostają możliwość budowania własnych nitek.",
    technology: "Supabase Auth · powiadomienia push i e-mail · system uprawnień i moderacji · publiczne profile · analityka reakcji z ochroną prywatności",
  },
  {
    number: "03", label: "PEŁNY SILNIK KONTEKSTU", title: "Model, który rozumie całą bazę",
    text: "Kompletujemy możliwie szerokie archiwa mediów, BIP-ów, instytucji, głosowań, nagrań i innych legalnie dostępnych źródeł. Własny model spin.clinic łączy zdarzenia, osoby, dokumenty i wypowiedzi w jedną historię. Nagrania otrzymują transkrypcje, a Dr Spin reaguje niemal na bieżąco.",
    technology: "własny model open source · RAG i graf wiedzy · video/audio-to-text · OCR dokumentów · pełny katalog BIP i źródeł instytucjonalnych · automatyczna kontrola jakości",
  },
];

export default function HowWeWorkPage() {
  return <article className="method-page">
    <header className="method-hero">
      <p className="method-kicker">CONTEXT BEFORE CONTENT</p>
      <h1>Najpierw źródło.<br />Potem kontekst.</h1>
      <p className="method-lead">Wiadomość rzadko zaczyna się w chwili, w której trafia na ekran. spin.clinic łączy materiały z wielu miejsc i układa je w czasie, żeby łatwiej było zobaczyć całą historię.</p>
    </header>
    <section className="method-principles" aria-labelledby="principles-title">
      <h2 id="principles-title">Proste zasady</h2>
      <div className="method-grid">
        <div><span>ŹRÓDŁO ZOSTAJE ŹRÓDŁEM</span><h3>Nie zastępujemy wydawców</h3><p>Pokazujemy autora, datę i link do oryginału. Zbieramy i przetwarzamy tylko taki zakres danych, na jaki pozwalają prawo, licencja albo zgoda właściciela.</p></div>
        <div><span>JEDNA METODA</span><h3>Bez taryfy ulgowej dla swoich</h3><p>Sprawdzamy konkretne zdanie, nie człowieka. Te same zasady obowiązują polityka, urząd, firmę i redakcję — niezależnie od poglądów autora projektu.</p></div>
        <div><span>WIDAĆ, CO SIĘ ZMIENIŁO</span><h3>Błąd poprawiamy publicznie</h3><p>Przy analizie pokazujemy dowody i braki. Można zgłosić nowe źródło lub poprosić o korektę, a istotne zmiany pozostają w historii.</p></div>
      </div>
    </section>
    <section className="method-stages" aria-labelledby="stages-title">
      <div className="method-section-intro"><p>DROGA DO PEŁNEGO SYSTEMU</p><h2 id="stages-title">Budujemy w trzech fazach</h2></div>
      {stages.map(stage => <div className="method-stage" key={stage.number}>
        <span>{stage.number}</span>
        <div className="method-stage-title"><small>{stage.label}</small><h3>{stage.title}</h3></div>
        <div><p>{stage.text}</p><p className="method-stage-tech"><strong>Technologia:</strong> {stage.technology}</p></div>
      </div>)}
    </section>
    <section className="method-limit" aria-labelledby="limits-title">
      <p>UCZCIWIE O OGRANICZENIACH</p><h2 id="limits-title">AI nie zna tego, czego nie zapisano</h2>
      <p>Model pracuje na odnalezionych danych. Nie zna prywatnych rozmów, cudzych intencji ani całego ludzkiego kontekstu. Może też nie znaleźć ważnego materiału lub źle połączyć zdarzenia. Dlatego oddzielamy fakt od opinii, zaznaczamy niepewność i nie obiecujemy nieomylności. Obiecujemy coś bardziej użytecznego: wynik, który można sprawdzić, zakwestionować i poprawić.</p>
    </section>
    <section className="method-tech" aria-labelledby="dr-spin-title">
      <div><p>DR SPIN</p><h2 id="dr-spin-title">Najpierw dowody, potem etykieta</h2></div>
      <p>Dr Spin wychwytuje sprawdzalne twierdzenie, rozkłada je na części i szuka materiałów za, przeciw oraz tych, które pokazują brakujący kontekst. AI przygotowuje kartę dowodową i szkic. W MVP decyzję o publikacji podejmuje redakcja spin.clinic. Wraz ze wzrostem jakości będziemy automatyzować jednoznaczne przypadki, pozostawiając możliwość szybkiej korekty.</p>
    </section>
    <footer className="method-owner">
      <p>KTO TO TWORZY</p><h2>Jedna osoba, wiele narzędzi AI, jedna jawna metoda</h2>
      <p>spin.clinic jest niezależnym projektem prowadzonym obecnie przez jedną osobę. Nie publikuję tu prywatnych danych ani szczegółowego życiorysu. Ważniejsze jest to, jak działa system: osobiste sympatie polityczne nie decydują o doborze źródeł ani wyniku analizy.</p>
      <small>Projekt i metodologia rozwijają się etapami. Przy każdej większej zmianie opiszemy, co potrafi system, czego jeszcze nie potrafi i jakich technologii używa.</small>
    </footer>
  </article>;
}
