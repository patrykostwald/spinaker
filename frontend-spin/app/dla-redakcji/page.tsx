import Link from "next/link";
import { DocLayout } from "@spin-clinic/ui/kit";
import { ContextThreadExample } from "./ContextThreadExample";

export const metadata = {
  title: "Dla redakcji — spin.clinic",
  description: "Jak cytować diagnozy AI, odsyłać do źródeł i metodologii oraz dołączyć do pilotażu autoryzowanych nitek.",
  alternates: { canonical: "/dla-redakcji" },
};

const sections = [
  { id: "cytowanie", label: "Cytowanie diagnozy" }, { id: "link", label: "Trwały link" },
  { id: "zrodla", label: "Źródła i metodologia" }, { id: "kontakt", label: "Kontakt" },
  { id: "pilotaz", label: "Pilotaż nitek" }, { id: "rss", label: "Zgoda na odczyt RSS" },
];

export default function PressPage() {
  const sourcesEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "zrodla@spin.clinic";
  const scope = [
    ["Co pobieramy", "Tytuł, autora, datę publikacji, link i nazwę źródła."],
    ["Skąd", "Ze wskazanego kanału RSS albo wskazanych stron publicznych."],
    ["Tempo", "Co najmniej 3 sekundy między zapytaniami i uzgodniony limit dzienny."],
    ["Zakres", "Bez pełnych tekstów, zdjęć ani kopii artykułów; nie trenujemy na nich modeli AI."],
    ["Czytelnik", "Widzi box ze źródłem, a po kliknięciu trafia do oryginału."],
    ["Zgoda", "Brak odpowiedzi nie jest zgodą — źródło pozostaje wyłączone."],
    ["Rezygnacja", "Wystarczy wiadomość, a wyłączymy źródło."],
  ];
  return <DocLayout eyebrow="DLA REDAKCJI" title="Korzystaj z analiz i źródeł" version="1.0" updatedAt="2026-09-29" sections={sections}
    lead="Diagnoza Dr. Spina może być punktem wyjścia do pracy dziennikarskiej. Cytuj konkretną analizę, zaznacz udział AI i sprawdź materiał źródłowy.">
    <section id="cytowanie"><h2>Jak cytować diagnozę</h2>
      <p>Podaj nazwę spin.clinic, tytuł i datę diagnozy oraz jej bezpośredni adres. Zaznacz, że analizę przygotowało AI. Rozróżniaj ocenę techniki perswazji od statusu sprawdzanego twierdzenia; zachowaj kontekst cytatu i ograniczenia wyniku.</p>
      <blockquote className="sc-doc-quote">Przykład zapisu: „Według analizy AI Dr. Spina w spin.clinic («[tytuł diagnozy]», [data diagnozy]) w tej wypowiedzi rozpoznano [technikę]. Źródło: [trwały adres diagnozy], dostęp: [data]”.</blockquote>
      <p>Wpis lub film spin.clinic w mediach społecznościowych jest skrótem analizy — przed cytowaniem otwórz pełną diagnozę i sprawdź materiał źródłowy. Uzupełnij pola danymi wybranej diagnozy. Jej siła 0–100 opisuje komunikat, nie osobę. Ocena AI nie zastępuje samodzielnej weryfikacji redakcyjnej.</p>
    </section>
    <section id="link"><h2>Trwały link</h2>
      <p>Otwórz konkretną diagnozę z <Link href="/klinika/diagnozy">archiwum</Link> i skopiuj adres jej strony: <code>https://spin.clinic/klinika/[id]</code>. Zachowuje on identyfikator analizy; adres strony głównej lub widok „spin dnia” nie wskazuje stale tego samego materiału.</p>
      <p>Zapisz również datę dostępu. Po wycofaniu diagnozy albo utracie dostępności wpisu treść może przestać być publicznie widoczna. Stały identyfikator nie jest gwarancją wieczystego dostępu.</p>
    </section>
    <section id="zrodla"><h2>Źródła i metodologia</h2>
      <p>Przy diagnozie są wpis wejściowy, cytaty i źródła do sprawdzanych twierdzeń. Otwórz oryginały i sprawdź, co rzeczywiście potwierdzają. <Link href="/zrodla">Katalog źródeł wiadomości</Link> to osobny wykaz; nie jest listą dowodów użytych w każdej diagnozie.</p>
      <p><Link href="/metodologia">Aktualna metodologia</Link> wyjaśnia sposób obliczeń i ograniczenia. <Link href="/konsylium">Konsylium AI</Link> pokazuje aktualny skład, a uczestników konkretnej analizy sprawdzisz przy jej wyniku. <Link href="/metodologia#korekty">Zasady wycofania diagnozy</Link>.</p>
    </section>
    <section id="kontakt"><h2>Kontakt z projektem</h2>
      <p>Współpraca i pytania mediów: <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Zgłoszenia błędów wraz z linkiem i dowodami: <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. Operator: iapply sp. z o.o.; <Link href="/o-nas#operator">dane operatora</Link>.</p>
    </section>
    <section id="pilotaz"><h2>Pilotaż autoryzowanych nitek</h2>
      <p>Zapraszamy redakcje i poszczególnych dziennikarzy do prowadzenia autoryzowanych nitek kontekstowych. To osobna forma współpracy: autor układa materiały i ich kolejność, podpisując nitkę nazwiskiem i redakcją. Materiały mediów pobieramy wyłącznie w uzgodnionym zakresie, za zgodą wydawcy.</p>
      <ContextThreadExample />
      <p>W sprawie pilotażu napisz na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>.</p>
    </section>
    <section id="rss"><h2>Zgoda na odczyt RSS</h2>
      <dl className="sc-doc-definitions">{scope.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}</dl>
      <p>Chętnie uwzględnimy wymagany sposób oznaczania źródła i limity techniczne. Kontakt w sprawie zgody: <a href={`mailto:${sourcesEmail}`}>{sourcesEmail}</a>.</p>
    </section>
  </DocLayout>;
}
