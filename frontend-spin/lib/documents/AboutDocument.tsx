import { DocumentLink as Link, documentTranslator, type DocumentLanguage } from "./locale";
import { DocLayout, GlitchWord, SpinExplainer } from "@spin-clinic/ui/kit";
import { socialChannels } from "@spin-clinic/ui";

export function AboutDocument({ lang = "pl" }: { lang?: DocumentLanguage }) {
  const t = documentTranslator(lang);
  const sections = [
    { id: "spin", label: t("Czym jest spin") }, { id: "projekt", label: t("Projekt") }, { id: "operator", label: t("Operator") },
    { id: "finansowanie", label: t("Finansowanie") }, { id: "obserwuj", label: t("Obserwuj nas") }, { id: "kontakt", label: t("Kontakt") },
    { id: "rozwoj", label: t("Co działa i co planujemy") },
  ];

  const sourcesEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "zrodla@spin.clinic";
  return <DocLayout lang={lang} alternateHref={lang === "pl" ? "/en/about" : "/o-nas"} eyebrow={t("O NAS")} title={lang === "pl" ? <>Ta sama <GlitchWord word="miara" /> dla wszystkich</> : t("Ta sama miara dla wszystkich")} version="1.0" updatedAt="2026-09-30" sections={sections}
    lead={t("spin.clinic łączy analizę konkretnych wypowiedzi ze źródłami i kontekstem do samodzielnego sprawdzenia.")}>
    <p className="sc-spin-explainer__title sc-spin-explainer__title--big sc-about-przekaz">{lang === "pl" ? <>Jak działa <GlitchWord word="przekaz" /></> : <>How the <GlitchWord word="message" /> works</>}</p>
    <SpinExplainer id="spin" text={{ kicker: t("Czym jest spin"), title: t("Politycy mają spin doktorów. Ty masz spin.clinic."), items: [
      { name: t("Spin"), text: t("Fakty podane tak, by działały na czyjąś korzyść: dobór słów, pominięcia, emocje. Nie zawsze kłamstwo, zawsze kierunek.") },
      { name: t("Spin doktor"), text: t("Doradca, który układa przekaz polityka: co powiedzieć, jak to ująć i co przemilczeć. Są po obu stronach sceny.") },
      { name: t("spin.clinic"), text: t("Strażnik po Twojej stronie: Konsylium AI rozkłada przekaz na techniki i sprawdza twierdzenia. Jedna miara dla wszystkich.") },
    ] }} />
    <section id="projekt"><h2>{t("Projekt")}</h2>
      <p>{t("spin.clinic pomaga czytać publiczne wypowiedzi ze świadomością tego, jak powstaje przekaz. Dr. Spin analizuje konkretne komunikaty polityków: wskazuje techniki perswazji, przytacza cytaty i zestawia twierdzenia ze źródłami. Rządzących i opozycję obejmują te same zasady. Obok Kliniki porządkujemy odnośniki do wiadomości, dokumentów i nagrań, zawsze z nazwą źródła, datą i linkiem do oryginału. Wyniki AI pokazujemy wraz z ograniczeniami, aby czytelnik mógł je sprawdzić i wyrobić własne zdanie. Wybrane diagnozy publikujemy także jako wpisy, grafiki i krótkie filmy w mediach społecznościowych - zawsze z linkiem do pełnej analizy. Projekt działa w wersji beta i rozwija się etapami.")}</p>
      <p><Link lang={lang} id="konsylium" href="/konsylium">{t("Jak wykorzystujemy AI")}</Link> · <Link lang={lang} id="klinika" href="/metodologia">{t("Metodologia analiz")}</Link> · <Link lang={lang} id="dla-redakcji" href="/dla-redakcji">{t("Informacje dla redakcji")}</Link> · <Link lang={lang} id="film" href="/konsylium#film">{t("Film o serwisie")}</Link></p>
    </section>
    <section id="operator"><h2>{t("Operator")}</h2>
      <p>{t("Operatorem serwisu jest iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488.")}</p>
    </section>
    <section id="finansowanie"><h2>{t("Finansowanie i niezależność")}</h2>
      <p>{t("Projekt finansuje operator, iapply sp. z o.o., przy wsparciu czytelników. Ponosimy koszty API X, płatnych etapów analiz AI, transkrypcji i utrzymania serwisu; część zadań działa w bezpłatnych limitach usług.")}</p>
      <p>{t("Nie przyjmujemy darowizn od partii, polityków ani ich fundacji. Dane i raporty sprzedajemy każdemu na tych samych warunkach. Żaden klient ani darczyńca nie ma wpływu na diagnozy, listę czytanych kont ani treści serwisu.")} <Link lang={lang} href="/wsparcie">{t("Koszty i wsparcie projektu")}</Link>.</p>
    </section>
    <section id="obserwuj"><h2>{t("Obserwuj nas")}</h2>
      <p>{t("Najsilniejsze diagnozy publikujemy automatycznie także poza stroną - zawsze z linkiem do pełnej analizy i źródeł, bez oznaczania polityków.")}</p>
      <ul className="sc-social-list">{socialChannels.map(channel => (
        <li key={channel.name}><a href={channel.href} target="_blank" rel="noopener noreferrer"><strong>{channel.name}</strong><span>{channel.handle}</span></a><p>{t(channel.what)}</p></li>
      ))}</ul>
    </section>
    <section id="kontakt"><h2>{t("Kontakt")}</h2>
      <ul>
        <li><a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a> {t("- projekt, współpraca, media, sprawy techniczne, prywatność i zgłoszenia dotyczące diagnoz.")}</li>
        <li><a href={`mailto:${sourcesEmail}`}>{sourcesEmail}</a> {t("- źródła, zgody wydawców i zakres dostępu.")}</li>
      </ul>
      <p>{t("Zgłaszając błąd, dołącz link do diagnozy i źródła.")} <Link lang={lang} href="/metodologia#korekty">{t("Jak obsługujemy zgłoszenia")}</Link>. {t("Wycofania, ukrycia prawne i odpowiedzi autorów:")} <Link lang={lang} href="/klinika/korekty">{t("Rejestr korekt")}</Link>.</p>
    </section>
    <section id="rozwoj"><h2>{t("Co działa i co planujemy")}</h2>
      <p>{t("Działa obecnie: diagnozy wypowiedzi polityków, analizy wywiadów, „Przekaz dnia” obu obozów, raporty tygodnia, dane i wykresy oraz publikacja wybranych diagnoz w mediach społecznościowych.")}</p>
      <ol>
        <li><strong>{t("Faza I - działa w wersji beta:")}</strong> {t("wiadomości, Klinika z Konsylium AI, wywiady, raporty, wykresy, filmy z diagnoz i pilotaż autoryzowanych tropów.")}</li>
        <li><strong>{t("Faza II - planowana:")}</strong> {t("konta i tropy czytelników, dyskusje oraz śledzenie zmian źródeł.")}</li>
        <li><strong>{t("Faza III - planowana:")}</strong> {t("własna maszyna do analiz na otwartych modelach, asystent oparty na bazie źródeł i aplikacje mobilne.")}</li>
      </ol>
      <p><Link lang={lang} href="/newsletter">{t("Newsletter o rozwoju projektu")}</Link>.</p>
    </section>
  </DocLayout>;
}
