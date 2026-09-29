import Link from "next/link";
import { DocLayout } from "@spin-clinic/ui/kit";
import { socialChannels } from "@spin-clinic/ui";

export const metadata = {
  title: "O nas — spin.clinic",
  description: "Projekt spin.clinic, operator, finansowanie, niezależność i kontakt. Pokazujemy, jak zbudowany jest przekaz.",
  alternates: { canonical: "/o-nas" },
};

const sections = [
  { id: "projekt", label: "Projekt" }, { id: "operator", label: "Autor i operator" },
  { id: "finansowanie", label: "Finansowanie" }, { id: "obserwuj", label: "Obserwuj nas" }, { id: "kontakt", label: "Kontakt" },
  { id: "rozwoj", label: "Co działa i co planujemy" },
];

export default function AboutPage() {
  const sourcesEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "zrodla@spin.clinic";
  return <DocLayout eyebrow="O NAS" title="Pokazujemy, jak zbudowany jest przekaz" version="1.0" updatedAt="2026-09-30" sections={sections}
    lead="spin.clinic łączy analizę konkretnych wypowiedzi ze źródłami i kontekstem do samodzielnego sprawdzenia.">
    <section id="projekt"><h2>Projekt</h2>
      <p>spin.clinic pomaga czytać publiczne wypowiedzi ze świadomością tego, jak powstaje przekaz. Dr. Spin analizuje konkretne komunikaty polityków: wskazuje techniki perswazji, przytacza cytaty i zestawia twierdzenia ze źródłami. Rządzących i opozycję obejmują te same zasady. Obok Kliniki porządkujemy odnośniki do wiadomości, dokumentów i nagrań, zawsze z nazwą źródła, datą i linkiem do oryginału. Wyniki AI pokazujemy wraz z ograniczeniami, aby czytelnik mógł je sprawdzić i wyrobić własne zdanie. Wybrane diagnozy publikujemy także jako wpisy, grafiki i krótkie filmy w mediach społecznościowych — zawsze z linkiem do pełnej analizy. Projekt działa w wersji beta i rozwija się etapami.</p>
      <p><Link id="konsylium" href="/konsylium">Jak wykorzystujemy AI</Link> · <Link id="klinika" href="/metodologia">Metodologia analiz</Link> · <Link id="dla-redakcji" href="/dla-redakcji">Informacje dla redakcji</Link> · <Link id="film" href="/konsylium#film">Film o serwisie</Link></p>
    </section>
    <section id="operator"><h2>Autor i operator</h2>
      <p>Projekt rozwija jedna osoba, korzystając z AI do programowania i analiz. Operatorem serwisu jest iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488.</p>
    </section>
    <section id="finansowanie"><h2>Finansowanie i niezależność</h2>
      <p>Projekt powstaje dzięki pracy twórcy i wsparciu czytelników. Ponosimy koszty API X, płatnych etapów analiz AI, transkrypcji i utrzymania serwisu; część zadań działa w bezpłatnych limitach usług.</p>
      <p>Nie przyjmujemy pieniędzy od partii, polityków ani ich fundacji. Wpłata nie daje wpływu na wybór materiałów ani wynik diagnozy. Nie mamy reklam ani sponsorów wpływających na treść. <Link href="/wsparcie">Koszty i wsparcie projektu</Link>.</p>
    </section>
    <section id="obserwuj"><h2>Obserwuj nas</h2>
      <p>Najsilniejsze diagnozy publikujemy automatycznie także poza stroną — zawsze z linkiem do pełnej analizy i źródeł, bez oznaczania polityków.</p>
      <ul className="sc-social-list">{socialChannels.map(channel => (
        <li key={channel.name}><a href={channel.href} target="_blank" rel="noopener noreferrer"><strong>{channel.name}</strong><span>{channel.handle}</span></a><p>{channel.what}</p></li>
      ))}</ul>
    </section>
    <section id="kontakt"><h2>Kontakt</h2>
      <ul>
        <li><a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a> — projekt, współpraca, media, sprawy techniczne, prywatność i zgłoszenia dotyczące diagnoz.</li>
        <li><a href={`mailto:${sourcesEmail}`}>{sourcesEmail}</a> — źródła, zgody wydawców i zakres dostępu.</li>
      </ul>
      <p>Zgłaszając błąd, dołącz link do diagnozy i źródła. <Link href="/metodologia#korekty">Jak obsługujemy zgłoszenia</Link>.</p>
    </section>
    <section id="rozwoj"><h2>Co działa i co planujemy</h2>
      <p>Działa obecnie: diagnozy wypowiedzi polityków, analizy wywiadów, „Przekaz dnia” obu obozów, raporty tygodnia, dane i wykresy oraz publikacja wybranych diagnoz w mediach społecznościowych.</p>
      <ol>
        <li><strong>Faza I — działa w wersji beta:</strong> wiadomości, Klinika z Konsylium AI, wywiady, raporty, wykresy, filmy z diagnoz i pilotaż autoryzowanych nitek kontekstowych.</li>
        <li><strong>Faza II — planowana:</strong> konta i nitki czytelników, dyskusje oraz śledzenie zmian źródeł.</li>
        <li><strong>Faza III — planowana:</strong> własna maszyna do analiz na otwartych modelach, asystent oparty na bazie źródeł i aplikacje mobilne.</li>
      </ol>
      <p><Link href="/newsletter">Newsletter o rozwoju projektu</Link>.</p>
    </section>
  </DocLayout>;
}
