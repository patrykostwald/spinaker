import { DocumentLink as Link, documentTranslator, type DocumentLanguage } from "./locale";
import { DocLayout } from '@spin-clinic/ui/kit';

export function CouncilCharterDocument({ lang = "pl" }: { lang?: DocumentLanguage }) {
  const t = documentTranslator(lang);
  const rules = [
    [
      t("Bez sympatii i bez antypatii."),
      t("Nie ma znaczenia, kto mówi, z jakiej partii jest i czy jego poglądy komuś odpowiadają.")
    ],
    [
      t("Badamy słowa, nie ludzi."),
      t("Diagnoza dotyczy konkretnej wypowiedzi: użytych technik, twierdzeń i słów. Nie oceniamy osoby, jej charakteru ani prawdomówności.")
    ],
    [
      t("Ta sama miara dla obu stron."),
      t("Rządzący i opozycja są oceniani według tych samych kryteriów, tą samą skalą i tymi samymi narzędziami.")
    ],
    [
      t("Nie zgadujemy intencji."),
      t("Nie przypisujemy autorowi zamiarów, których nie da się wykazać na podstawie tekstu.")
    ],
    [
      t("Każde twierdzenie ma status."),
      t("Potwierdzone, sprzeczne ze źródłami, wprowadzające w błąd albo niezweryfikowane. Ocena faktu wymaga źródła. Grupa nazywana w zestawieniach opiniami obejmuje dziś także twierdzenia, których nie udało się sprawdzić.")
    ],
    [
      t("Cytujemy wiernie."),
      t("Nie wyolbrzymiamy ani nie łagodzimy słów autora. Streszczenie zachowuje siłę oryginału.")
    ],
    [
      t("Mówimy, co zbadaliśmy."),
      t("Zakres analizy jest jawny (tekst, obraz, film) - czego nie zbadano, piszemy wprost.")
    ],
    [
      t("Pokazujemy różnice zdań."),
      t("Jeśli członkowie Konsylium się nie zgadzają, widać to na diagnozie (zgodność werdyktu, rozrzut ocen).")
    ],
    [
      t("Opublikowanej diagnozy nie edytuje się ręcznie."),
      t("Publikacja jest automatyczna. Człowiek może diagnozę tylko wycofać, nie zmienić jej treści.")
    ],
    [
      t("Prawo do korekty i odpowiedzi."),
      t("Każdy może zgłosić błąd lub przesłać odpowiedź. Dziś operator może ukryć całą diagnozę, zapisując datę i powód. Publiczny, datowany rejestr korekt i odpowiedzi jest zasadą docelową, jeszcze niewdrożoną.")
    ],
    [
      t("Jawny skład."),
      t("Publikujemy, które modele i narzędzia, w jakich wersjach i rolach stawiają diagnozy.")
    ],
    [
      t("Niezależność od pieniędzy politycznych."),
      t("spin.clinic nie przyjmuje pieniędzy od partii ani polityków; wsparcie czytelników nie wpływa na diagnozy.")
    ]
  ];
  const sections = [
    { id: 'zasady', label: t('Zasady') },
    { id: 'przyjecie', label: t('Stan przyjęcia Karty') },
    { id: 'zgloszenie', label: t('Zgłoś błąd') },
  ];

  return <DocLayout lang={lang} alternateHref={lang === "pl" ? "/en/council/charter" : "/konsylium/karta"} eyebrow={t("KONSYLIUM AI")} title={t("Karta Konsylium AI")} version="1.1" updatedAt="2026-09-29" sections={sections}
    lead={t("Zasady pracy modeli analizujących konkretne wypowiedzi. Wersja 1.1 doprecyzowuje statusy twierdzeń i obecne możliwości obsługi błędów.")}>
    <section id="zasady"><h2>{t("Zasady")}</h2><ol>{rules.map(([title, text]) => <li key={title}><strong>{title}</strong> {text}</li>)}</ol></section>
    <section id="przyjecie"><h2>{t("Stan przyjęcia Karty")}</h2>
      <p>{t("Nie deklarujemy, że każdy model przyjął Kartę. Rejestr pokazuje zapisane oświadczenia konkretnych wersji modeli, datę i wersję dokumentu, którego dotyczy odpowiedź. Brak oświadczenia oznacza oczekiwanie na jego zapisanie. Oświadczenie modelu nie jest podpisem ani poparciem jego twórcy lub dostawcy.")}</p>
      <p>{t("Pełny, aktualny wykaz jest w")} <Link lang={lang} href="/konsylium#sklad">{t("składzie Konsylium")}</Link>{t(". Oświadczenie dotyczące wcześniejszej wersji nie potwierdza przyjęcia wersji 1.1. Zasady są także częścią instrukcji analizy; sam wpis w rejestrze nie gwarantuje ich przestrzegania w każdym wyniku.")}</p>
    </section>
    <section id="zgloszenie"><h2>{t("Zgłoś błąd lub odpowiedź")}</h2>
      <p>{t("Wyślij link do diagnozy, opis błędu i źródła na")} <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>{t(". Operator może ukryć całą diagnozę, zapisując datę i powód; nie zmienia jej treści. Publiczna historia korekt i odpowiedzi pozostaje planem.")}</p>
      <p><Link lang={lang} href="/metodologia#korekty">{t("Obecny sposób obsługi błędów")}</Link> · <Link lang={lang} href="/konsylium">{t("Jak działa Konsylium AI")}</Link></p>
    </section>
  </DocLayout>;
}
