import { DocumentLink as Link, documentTranslator, type DocumentLanguage } from "./locale";
import { Button, DocLayout } from "@spin-clinic/ui/kit";
import { ReportContact, ReportSample } from "../../app/dla-redakcji/InstitutionReports";

export function PressDocument({ lang = "pl" }: { lang?: DocumentLanguage }) {
  const t = documentTranslator(lang);
  const text = (pl: string, en: string) => lang === "pl" ? pl : en;
  const sections = [
    { id: "dane", label: t("Dane i raporty") }, { id: "cytowanie", label: t("Cytowanie diagnozy") }, { id: "link", label: t("Trwały link") },
    { id: "zrodla", label: t("Źródła i metodologia") }, { id: "kontakt", label: t("Kontakt") },
    { id: "rss", label: t("Zgoda na odczyt RSS") },
  ];

  const sourcesEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "zrodla@spin.clinic";
  const scope = [
    [t("Co pobieramy"), t("Tytuł, autora, datę publikacji, link i nazwę źródła.")],
    [t("Skąd"), t("Ze wskazanego kanału RSS albo wskazanych stron publicznych.")],
    [t("Tempo"), t("Co najmniej 3 sekundy między zapytaniami i uzgodniony limit dzienny.")],
    [t("Zakres"), t("Bez pełnych tekstów, zdjęć ani kopii artykułów; nie trenujemy na nich modeli AI.")],
    [t("Czytelnik"), t("Widzi boks ze źródłem, a po kliknięciu trafia do oryginału.")],
    [t("Zgoda"), t("Brak odpowiedzi nie jest zgodą - źródło pozostaje wyłączone.")],
    [t("Rezygnacja"), t("Wystarczy wiadomość, a wyłączymy źródło.")],
  ];
  return <DocLayout lang={lang} alternateHref={lang === "pl" ? "/en/press" : "/dla-redakcji"} eyebrow={t("DLA REDAKCJI")} title={t("Dane i raporty o przekazie politycznym")} version="1.2" updatedAt="2026-10-09" className="sc-press-page" sections={sections}
    lead={text("Raporty o przekazie rządzących i opozycji oraz dane do własnych analiz. Jedna metoda oceny dla wszystkich obozów.", "Reports on government and opposition messaging, with data for your own analysis. The same assessment method for every political camp.")}>
    <section id="dane" className="sc-press-offer"><h2>{text("Raporty dla redakcji i instytucji", "Reports for newsrooms and institutions")}</h2>
      <div className="sc-rep-grid sc-press-products">
        <article className="sc-rep-box sc-press-product">
          <h3>{text("Raport tygodniowy", "Weekly report")}</h3>
          <p>{text("Przekaz rządzących i opozycji za poprzedni pełny tydzień.", "Government and opposition messaging over the previous full week.")}</p>
          <p className="sc-rep-box__foot">{text("PDF i CSV: diagnozy, techniki, trendy i metoda.", "PDF and CSV: diagnoses, techniques, trends and method.")}</p>
        </article>
        <article className="sc-rep-box sc-press-product">
          <h3>{text("Raport i dane", "Report and data")}</h3>
          <p>{text("Raport tygodniowy z zestawieniem tematu i danymi do własnych analiz.", "A weekly report with a topic overview and data for your own analysis.")}</p>
          <p className="sc-rep-box__foot">{text("Zestawienie miesięczne i dane CSV z archiwum diagnoz.", "Monthly overview and CSV data from the diagnosis archive.")}</p>
        </article>
      </div>
      <div className="sc-press-upcoming">
        {[text("Alerty", "Alerts"), text("Aplikacja", "App")].map(name => <div key={name}><h3>{name}</h3><span>{text("W przygotowaniu", "In preparation")}</span></div>)}
      </div>
      <p>{t("Jedna oferta dla wszystkich: te same produkty i warunki niezależnie od obozu politycznego. Klient nie ma wpływu na metodę, diagnozy ani treści serwisu. Sprzedajemy nasze analizy, nie cudze treści.")}</p>
      {lang === "pl" ? <><ReportSample /><ReportContact /></> :
        <p><Button href="mailto:kontakt@iapply.pl" variant="primary">Ask about a report</Button></p>}
    </section>
    <section id="cytowanie"><h2>{t("Jak cytować diagnozę")}</h2>
      <p>{t("Podaj nazwę spin.clinic, tytuł i datę diagnozy oraz jej bezpośredni adres. Zaznacz, że analizę przygotowało AI. Rozróżniaj ocenę techniki perswazji od statusu sprawdzanego twierdzenia. Zachowaj kontekst cytatu i ograniczenia wyniku.")}</p>
      <blockquote className="sc-doc-quote">{t("Przykład zapisu: „Według analizy AI Dr. Spina w spin.clinic («[tytuł diagnozy]», [data diagnozy]) w tej wypowiedzi rozpoznano [technikę]. Źródło: [trwały adres diagnozy], dostęp: [data]”.")}</blockquote>
      <p>{t("Wpis lub film spin.clinic w mediach społecznościowych jest skrótem analizy. Przed cytowaniem otwórz pełną diagnozę i sprawdź materiał źródłowy. Uzupełnij pola danymi wybranej diagnozy. Jej siła 0-100 opisuje komunikat, nie osobę. Ocena AI nie zastępuje samodzielnej weryfikacji redakcyjnej.")}</p>
    </section>
    <section id="link"><h2>{t("Trwały link")}</h2>
      <p>{t("Otwórz konkretną diagnozę z")} <Link lang={lang} href="/klinika/diagnozy">{t("archiwum")}</Link> {t("i skopiuj jej adres:")} <code>https://spin.clinic/klinika/[id]</code>{t(". Zachowuje on identyfikator analizy. Adres strony głównej lub widok „spin dnia” nie wskazuje stale tego samego materiału.")}</p>
      <p>{t("Zapisz również datę dostępu. Po wycofaniu diagnozy albo utracie dostępności wpisu treść może przestać być publicznie widoczna. Stały identyfikator nie jest gwarancją wieczystego dostępu.")}</p>
    </section>
    <section id="zrodla"><h2>{t("Źródła i metodologia")}</h2>
      <p>{t("Przy diagnozie znajdziesz wpis wejściowy, cytaty i źródła do sprawdzanych twierdzeń. Otwórz oryginały i sprawdź, co rzeczywiście potwierdzają.")} <Link lang={lang} href="/zrodla">{t("Katalog źródeł")}</Link> {t("to osobny wykaz. Nie jest listą dowodów użytych w każdej diagnozie.")}</p>
      <p><Link lang={lang} href="/metodologia">{t("Aktualna metodologia")}</Link> {t("wyjaśnia sposób obliczeń i ograniczenia.")} <Link lang={lang} href="/konsylium">{t("Konsylium AI")}</Link> {t("pokazuje aktualny skład, a uczestników konkretnej analizy sprawdzisz przy jej wyniku.")} <Link lang={lang} href="/metodologia#korekty">{t("Zasady wycofania diagnozy")}</Link>.</p>
    </section>
    <section id="kontakt"><h2>{t("Kontakt z projektem")}</h2>
      <p>{t("Współpraca i pytania mediów:")} <a href="mailto:kontakt@iapply.pl">kontakt@iapply.pl</a>{t(". Zgłoszenia błędów (z linkiem i dowodami):")} <a href="mailto:kontakt@iapply.pl">kontakt@iapply.pl</a>. Operator: iapply sp. z o.o.; <Link lang={lang} href="/o-nas#operator">{t("dane operatora")}</Link>.</p>
    </section>
    <section id="rss"><h2>{t("Zgoda na odczyt RSS")}</h2>
      <dl className="sc-doc-definitions">{scope.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}</dl>
      <p>{t("Chętnie uwzględnimy wymagany sposób oznaczania źródła i limity techniczne. Kontakt w sprawie zgody:")} <a href={`mailto:${sourcesEmail}`}>{sourcesEmail}</a>.</p>
    </section>
  </DocLayout>;
}
