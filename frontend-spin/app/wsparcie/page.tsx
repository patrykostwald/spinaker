import { Button, InfoPage } from '@spin-clinic/ui/kit';

export const metadata = { title: 'Wsparcie · spin.clinic' };
// Linki BUYCOFFEE_URL i PATRONITE_URL czytamy z .env.production przy każdym wejściu, nie przy budowaniu obrazu.
export const dynamic = 'force-dynamic';

function publicSupportUrl(value: string | undefined) {
  try {
    const url = new URL(value || '');
    return url.protocol === 'https:' ? url.toString() : '';
  } catch {
    return '';
  }
}

export default function SupportPage() {
  const buycoffee = publicSupportUrl(process.env.BUYCOFFEE_URL);
  const patronite = publicSupportUrl(process.env.PATRONITE_URL);
  const links = [
    buycoffee && { label: 'Wesprzyj przez BuyCoffee', href: buycoffee },
    patronite && { label: 'Wesprzyj przez Patronite', href: patronite },
  ].filter(Boolean) as { label: string; href: string }[];

  return <InfoPage eyebrow="WSPARCIE" title="Politycy mają spin doktorów. My mamy spin.clinic." lead="spin.clinic to niezależny projekt, który pokazuje wiadomości ze źródłami i rozkłada przekazy polityków na czynniki pierwsze. Utrzymują go wyłącznie czytelnicy — bez reklam, sponsorów i partyjnych pieniędzy.">
    <section><h2>Kto za tym stoi</h2><p>Projekt buduje jedna osoba, która nie jest i nigdy nie była członkiem żadnej partii politycznej, redakcji ani organizacji politycznej. Nie reprezentuje żadnego obozu. Cały serwis powstaje przy wsparciu narzędzi sztucznej inteligencji — od kodu po analizę przekazów — i jest odpowiedzią na prostą nierówność: politycy mają zespoły od wizerunku, a obywatele zwykle nie mają nikogo.</p></section>
    <section><h2>Na co idą pieniądze</h2><p>Każda diagnoza spinu to realny koszt. Posty polityków pobieramy z płatnego API X, strażnik ocenia je darmowymi modelami, a każdą pełną diagnozę ze źródłami przygotowuje płatny model AI. Do tego serwer, baza i domena. Dziś pokrywamy te koszty sami — dlatego każda złotówka realnie przekłada się na liczbę sprawdzonych wypowiedzi.</p></section>
    <section><h2>Dokąd zmierzamy</h2><p>Naszym celem jest własny serwer i otwarte modele AI, uruchomione u nas i opisane jawnie. Dzięki temu Klinika spinu nie będzie zależna od zewnętrznych dostawców, a koszt jednej diagnozy spadnie niemal do zera. Wsparcie przybliża ten moment.</p></section>
    <section><h2>Wybierz sposób wsparcia</h2>{links.length ? <><p>Wpłaty obsługują oficjalne serwisy zewnętrzne. spin.clinic nie przetwarza danych płatniczych.</p><div className="sc-info-page__actions">{links.map(link => <Button key={link.href} href={link.href} variant="primary">{link.label}</Button>)}</div></> : <p>Linki do BuyCoffee i Patronite pojawią się tutaj wkrótce. Nie pobieramy płatności bezpośrednio w serwisie.</p>}</section>
    <section><h2>Dziękujemy</h2><p>Nawet jednorazowa kawa to kilka kolejnych sprawdzonych wypowiedzi. Jeśli nie możesz wesprzeć finansowo, udostępnij diagnozę z Kliniki na X — to też bardzo pomaga.</p></section>
  </InfoPage>;
}
