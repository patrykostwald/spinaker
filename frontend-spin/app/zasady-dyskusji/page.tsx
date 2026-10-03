import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Zasady dyskusji | spin.clinic" };

export default function DiscussionRules() {
  return <article className="sc-discussion-rules">
    <h1>Zasady dyskusji</h1>
    <p>Dyskutujemy o przekazie i analizach, z szacunkiem dla rozmówców. Możesz zgadzać się z diagnozą lub ją krytykować - ocena jest niezależna od komentarza.</p>
    <ul>
      <li>Pisz kulturalnie: bez wulgaryzmów, gróźb, mowy nienawiści i spamu.</li>
      <li>Nie publikuj danych prywatnych - swoich ani innych osób.</li>
      <li>Ta sama miara obowiązuje wszystkich, niezależnie od poglądów politycznych.</li>
      <li>Moderacja ocenia zachowanie, nigdy poglądy. Może ukryć komentarz lub czasowo zablokować komentowanie. Nie edytuje treści komentarzy ani diagnoz AI.</li>
    </ul>
    <h2>Dyskusje pod diagnozami i wywiadami w Klinice</h2>
    <p>Komentować i oceniać można po zalogowaniu oraz potwierdzeniu e-maila. Komentarz mieści do 1000 znaków; odpowiedzi mają jeden poziom. Limit to 10 komentarzy na godzinę i 50 na dobę, z odstępem co najmniej 30 sekund. Powtórzenie tego samego komentarza jest blokowane.</p>
    <p>Nowe komentarze sprawdza automatyczny filtr. Wskazane naruszenia trafiają do zespołu spin.clinic jako ukryte komentarze. Jeśli filtr nie odpowie, komentarz zostaje opublikowany i oznaczony do przeglądu. Trzy niezależne zgłoszenia ukrywają komentarz do decyzji moderatora. Autor widzi swój ukryty komentarz wraz z powodem.</p>
    <p>Przycisk „Zgłoś” służy do wskazywania naruszeń. Jeśli chcesz wyjaśnić decyzję moderacji, napisz do <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>, podając numer komentarza. Operator serwisu: iapply sp. z o.o.</p>
    <h2>Spinki</h2><p>Pod spinką komentarze tworzą płaską listę i mają limit 2000 znaków (krótki komentarz do 280). Możesz wskazać @boks 3, edytować przez 5 minut i usunąć swój komentarz później. Limit to 20 zapisów komentarzy i 50 zapisów ocen na godzinę. Jeden głos na spinkę można zmieniać. Zgłoszenia sprawdza zespół z pomocą AI; decyzja zawiera uzasadnienie i możliwość jednego odwołania rozpatrywanego przez człowieka.</p>
    <p><Link href="/zasady-korzystania#tropy">Pełne zasady spinek, ocen i komentarzy oraz punkt kontaktowy</Link></p>
    <p><Link href="/klinika">Wróć do Kliniki</Link></p>
  </article>;
}
