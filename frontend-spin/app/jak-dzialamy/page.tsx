import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Jak działamy — spin.clinic",
  description: "Źródła, metoda, ograniczenia i etapy rozwoju spin.clinic.",
};

const stages = [
  {
    number: "01",
    title: "Archiwum i kontekst",
    text: "Zbieramy dozwolone metadane z publicznych źródeł, zachowujemy odnośnik do oryginału i łączymy publikacje dotyczące tego samego zdarzenia. Każdy materiał pozostaje przypisany do wydawcy.",
  },
  {
    number: "02",
    title: "Dr Spin i praca redakcyjna",
    text: "System wykrywa sprawdzalne twierdzenia, szuka źródeł pierwotnych i przygotowuje kartę dowodową. W pierwszym etapie publiczną ocenę zatwierdza redakcja spin.clinic, a korekty pozostają widoczne.",
  },
  {
    number: "03",
    title: "Własny model kontekstu",
    text: "Docelowy model ma rozumieć zależności między materiałami i wydarzeniami z naszej bazy. Będzie rozwijany na danych, do których mamy odpowiednie prawa, z testami jakości i nadzorem człowieka.",
  },
];

export default function HowWeWorkPage() {
  return <article className="method-page">
    <header className="method-hero">
      <p className="method-kicker">CONTEXT BEFORE CONTENT</p>
      <h1>Jak działamy</h1>
      <p className="method-lead">spin.clinic porządkuje publiczne informacje i pokazuje kontekst, zanim powstanie ocena. Projekt jest rozwijany niezależnie przez jedną osobę przy wsparciu narzędzi AI.</p>
    </header>

    <section className="method-principles" aria-labelledby="principles-title">
      <h2 id="principles-title">Nasze zasady</h2>
      <div className="method-grid">
        <div><span>ŹRÓDŁA</span><h3>Materiał prowadzi do oryginału</h3><p>Box pokazuje wydawcę, datę i odnośnik. AI pomaga szukać i porządkować; nie staje się źródłem faktu.</p></div>
        <div><span>METODA</span><h3>Te same kryteria dla każdego</h3><p>Sprawdzamy konkretne twierdzenia oraz dowody, niezależnie od osoby, partii czy redakcji.</p></div>
        <div><span>KOREKTY</span><h3>Wynik można zakwestionować</h3><p>Pokazujemy uzasadnienie, wykorzystane źródła i historię zmian. Brakujące źródło lub błąd można zgłosić.</p></div>
      </div>
    </section>

    <section className="method-stages" aria-labelledby="stages-title">
      <div className="method-section-intro"><p>PLAN ROZWOJU</p><h2 id="stages-title">Trzy etapy</h2></div>
      {stages.map(stage => <div className="method-stage" key={stage.number}>
        <span>{stage.number}</span><h3>{stage.title}</h3><p>{stage.text}</p>
      </div>)}
    </section>

    <section className="method-limit" aria-labelledby="limits-title">
      <p>JAWNE OGRANICZENIA</p>
      <h2 id="limits-title">Kontekst nigdy nie jest kompletny</h2>
      <p>Model widzi tylko dane, które zostały opublikowane, odnalezione i prawidłowo połączone. Nie zna niewypowiedzianych intencji, prywatnych rozmów ani całego ludzkiego kontekstu. Dlatego wskazujemy braki, poziom pewności i rozróżniamy fakt, opinię oraz twierdzenie nieweryfikowalne. Nie obiecujemy nieomylności — obiecujemy sprawdzalny proces i korektę błędów.</p>
    </section>

    <section className="method-tech" aria-labelledby="tech-title">
      <div><p>TECHNOLOGIA</p><h2 id="tech-title">Co pracuje pod spodem</h2></div>
      <p>Publiczne i legalnie dostępne źródła, własna baza danych, automaty zbierające metadane, wyszukiwanie semantyczne oraz modele AI wspierające klasyfikację i łączenie materiałów. Dostawcy mogą się zmieniać; źródła, decyzje i wyniki testów pozostają pod kontrolą spin.clinic.</p>
    </section>

    <footer className="method-owner">
      <p>O PROJEKCIE</p>
      <h2>Niezależnie od sympatii politycznych</h2>
      <p>Projekt prowadzi jedna osoba. Nie publikujemy tu danych osobistych ani prywatnych szczegółów. Osobiste poglądy autora nie są kryterium doboru źródeł lub oceny wypowiedzi; obowiązuje opisana metoda, jawne dowody i możliwość korekty.</p>
      <small>Metodologia będzie aktualizowana wraz z rozwojem projektu. Każda istotna zmiana otrzyma datę i opis.</small>
    </footer>
  </article>;
}
