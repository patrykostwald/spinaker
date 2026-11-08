import { InfoPage } from '@spin-clinic/ui/kit';
import { TERMS_VERSION } from '@spin-clinic/ui';

const contact = process.env.CONTACT_EMAIL || 'kontakt@spin.clinic';

export const metadata = { title: 'Zasady korzystania · spin.clinic' };

export default function TermsPage() {
  return <InfoPage eyebrow="INFORMACJE" title="Zasady korzystania" lead="spin.clinic porządkuje i łączy odnośniki do materiałów źródłowych. Nie zastępuje publikacji wydawcy ani samodzielnej oceny czytelnika.">
    <p>Wersja zasad: {TERMS_VERSION}.</p>
    <section><h2>Konto użytkownika</h2><p>Konto może założyć osoba, która ukończyła 18 lat i akceptuje zasady korzystania. Utworzenie konta oznacza zawarcie umowy o świadczenie usług konta. Zapis na newsletter jest dobrowolny i wymaga osobnej zgody. Nick jest publiczny i można go zmienić raz na 30 dni.</p></section>
    <section><h2>Materiały i kontekst</h2><p>Karta materiału pokazuje materiał, jego źródło, datę i odnośnik do oryginału. Powiązanie po haśle, kategorii, źródle lub czasie jest wskazówką do dalszego czytania, a nie dowodem, że jeden materiał potwierdza drugi. Dr. Spin przedstawia wybór i kolejność materiałów zatwierdzone przez zespół spin.clinic.</p></section>
    <section><h2>Klinika spinu</h2><p>Diagnozy wpisów polityków przygotowuje i publikuje automatycznie AI - każda jest tak oznaczona, z nazwą modelu i wersją instrukcji. Zasady publikacji i korekt opisuje <a href="/konsylium/karta">Karta Konsylium</a>. Diagnoza opisuje komunikat - techniki perswazji i zgodność twierdzeń ze źródłami - a nie osobę. AI przypisuje twierdzeniom status: potwierdzone, sprzeczne ze źródłami, wprowadzające w błąd albo niezweryfikowane - ustalenia o faktach mają linki do źródeł. Brak źródła oznacza brak weryfikacji, nie fałsz. Zgłoszenia dotyczące diagnoz przyjmujemy pod adresem <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>; po zgłoszeniu prawnym diagnoza może zostać ukryta.</p></section>
    <section><h2>Czego portal nie robi</h2><p>Nie ocenia osób ani ich prawdomówności, nie ogłasza, że wypowiedź „jest kłamstwem” - ocenia konkretny komunikat i status poszczególnych twierdzeń, nie publikuje treści modeli bez wyraźnego oznaczenia, że przygotowało je AI, i nie zastępuje oryginalnej publikacji. Jeśli czegoś nie wiemy, pokazujemy brak danych zamiast dopowiadać.</p></section>
    <section><h2>Źródła i prawa wydawców</h2><p>Szanujemy zasady dostępu do źródeł. Nie obchodzimy blokad, limitów ani płatnych dostępów. Pokazujemy konieczny opis i link do materiału; pełne teksty oraz inne utwory pozostają po stronie wydawcy, chyba że zakres wykorzystania jest wyraźnie dozwolony.</p></section>
    <section><h2>Materiały z platform</h2><p>Wpisy z X mogą służyć jako materiał źródłowy po ręcznym potwierdzeniu konta i przez oficjalne API. W przypadku YouTube wykorzystujemy dozwolone metadane i opis filmu. Wybrane wywiady przekazujemy do Gemini, które przygotowuje transkrypcję na potrzeby osobnej analizy wypowiedzi gościa oraz pytań i reakcji prowadzącego; automatyczna transkrypcja może zawierać błędy.</p></section>
    <section id="dyskusja"><h2>Komentarze i oceny w Klinice</h2>
      <p>Możesz komentować diagnozy, przekazy dnia i wywiady. Odpowiadasz za treść swoich komentarzy. Publikuj materiały, do których masz prawo, oraz linki do źródeł. Te same zasady stosujemy do wszystkich, niezależnie od poglądów.</p>
      <ul>
        <li><strong>N1. Treści bezprawne.</strong> Nie publikuj treści naruszających prawo, w tym cudze prawa autorskie.</li>
        <li><strong>N2. Groźby i nienawiść.</strong> Nie groź innym i nie nawołuj do nienawiści lub przemocy.</li>
        <li><strong>N3. Prywatność i tożsamość.</strong> Nie ujawniaj danych prywatnych i nie podszywaj się pod inne osoby.</li>
        <li><strong>N4. Spam.</strong> Nie publikuj spamu ani powtarzanych reklam.</li>
        <li><strong>N5. Brak naruszenia.</strong> Krytyka, wątpliwości i odmienne poglądy same w sobie nie są podstawą ukrycia treści.</li>
      </ul>
      <p>Komentowanie i ocenianie wymaga zalogowania oraz potwierdzonego adresu e-mail. Komentarz ma do 1000 znaków, a odpowiedzi jeden poziom. Obowiązuje odstęp co najmniej 30 sekund między komentarzami oraz limity 10 komentarzy na godzinę i 50 na dobę na konto. Powtórzenie tego samego komentarza jest blokowane. Te same możliwości i zasady obowiązują pod przekazami rządzących i opozycji.</p>
      <p>Ocena materiału jest niezależna od komentarza i nie zmienia diagnozy AI. Krytyka analizy, polityka lub partii nie jest sama w sobie naruszeniem. Moderacja ocenia zachowanie, nie poglądy, i ukrywa komentarze zamiast je edytować.</p>
      <p>Naruszenie zgłosisz przyciskiem „Zgłoś” przy komentarzu. Bez konta możesz napisać do punktu kontaktowego: <a href={`mailto:${contact}`}>{contact}</a>, podając link, powód i opis. Odpowiadamy po polsku. Zgłoszenia przeglądamy bez zbędnej zwłoki.</p>
      <p>Nowe komentarze sprawdza filtr AI. Wykryte naruszenie może spowodować ukrycie komentarza do przeglądu przez człowieka. Jeśli filtr nie odpowie, komentarz zostaje opublikowany i oznaczony do przeglądu. Trzy niezależne zgłoszenia również ukrywają komentarz do czasu decyzji moderatora. Zespół otrzymuje powiadomienia o nowych zgłoszeniach i odwołaniach.</p>
      <p>Autor widzi własny ukryty komentarz i powód ukrycia. Może raz na komentarz użyć przycisku „Odwołaj się”. Odwołanie trafia do kolejki przeglądu człowieka, który może przywrócić komentarz albo utrzymać jego ukrycie. Status odwołania jest widoczny przy komentarzu. Możesz także napisać do punktu kontaktowego.</p>
      <p>Szczegóły opisują <a href="/zasady-dyskusji">zasady dyskusji</a>.</p>
    </section>
    <section><h2>Operator serwisu</h2><p>Serwis spin.clinic prowadzi iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488. Kontakt: <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>.</p></section>
    <section><h2>Wersja beta</h2><p>Funkcje i zasady są rozwijane etapami. Przed zakończeniem bety opublikujemy wersję końcową wraz z datą wejścia w życie.</p></section>
  </InfoPage>;
}
