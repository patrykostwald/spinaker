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
    <h2>Dyskusje w Klinice</h2>
    <p>Komentarze są dostępne pod diagnozami, przekazami dnia i wywiadami. Przekazy rządzących i opozycji mają identyczne możliwości dyskusji i zasady moderacji.</p>
    <p>Komentowanie i ocenianie wymaga zalogowania oraz potwierdzenia adresu e-mail. Komentarz mieści do 1000 znaków; odpowiedzi mają jeden poziom. Limit: 10 komentarzy na godzinę i 50 na dobę, z odstępem co najmniej 30 sekund między wpisami. Powtórzenie tego samego komentarza jest blokowane.</p>
    <p>Nowe komentarze sprawdza automatyczny filtr AI. Zgłoszenia i odwołania przegląda człowiek. Wskazane naruszenia trafiają do zespołu spin.clinic jako ukryte komentarze. Jeśli filtr nie odpowie, komentarz zostaje opublikowany i oznaczony do przeglądu. Trzy niezależne zgłoszenia ukrywają komentarz do czasu decyzji moderatora. Autor widzi swój ukryty komentarz wraz z powodem.</p>
    <p>Przycisk „Zgłoś” służy do wskazywania naruszeń. Zgłoszenia przeglądamy bez zbędnej zwłoki. Zespół otrzymuje powiadomienia o nowych zgłoszeniach i odwołaniach.</p>
    <h2>Odwołanie od ukrycia komentarza</h2>
    <p>Przy własnym ukrytym komentarzu wybierz „Odwołaj się”. Możesz złożyć jedno odwołanie na komentarz. Trafi ono do kolejki przeglądu człowieka; jego status zobaczysz przy komentarzu. Moderator może przywrócić komentarz lub utrzymać ukrycie.</p>
    <p>W sprawach moderacji możesz też napisać na <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>, podając link lub numer komentarza. Operator serwisu: iapply sp. z o.o.</p>
    <p><Link href="/zasady-korzystania#dyskusja">Pełne zasady komentarzy, ocen i punkt kontaktowy</Link></p>
    <p><Link href="/klinika">Wróć do Kliniki</Link></p>
  </article>;
}
