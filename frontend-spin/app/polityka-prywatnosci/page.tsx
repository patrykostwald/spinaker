import { InfoPage } from '@spin-clinic/ui/kit';

export const metadata = { title: 'Prywatność i cookies · spin.clinic' };

export default function PrivacyPage() {
  return <InfoPage eyebrow="INFORMACJE" title="Prywatność i cookies" lead="Informacja dla wersji beta. Przed jej zakończeniem uzupełnimy okresy przechowywania i aktualną listę dostawców.">
    <section><h2>Administrator danych</h2><p>Administratorem danych osobowych w serwisie spin.clinic jest iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488. W sprawach prywatności napisz na <a href="mailto:admin@spin.clinic">admin@spin.clinic</a>.</p></section>
    <section><h2>Jakie dane mogą pojawić się w serwisie</h2><p>Bez logowania strona zapisuje tylko ustawienia potrzebne do działania interfejsu na danym urządzeniu, na przykład wybrany motyw. Po udostępnieniu kont użytkownik może podać nazwę użytkownika, opcjonalny adres e-mail i hasło; hasło jest przechowywane wyłącznie w postaci zabezpieczonego skrótu. Konto może zapisywać ulubione materiały, prywatne nitki kontekstowe, reakcje, komentarze i zgłoszenia.</p></section>
    <section><h2>Po co je przetwarzamy</h2><p>Dane konta służą do zalogowania, ochrony przed nadużyciami i działania funkcji wybranych przez użytkownika. Komentarze oraz zgłoszenia służą moderacji. Prywatne nitki nie są publiczne ani nie są przekazywane modelom AI jako materiał do analizy.</p></section>
    <section><h2>Materiały ze źródeł i zewnętrzne usługi</h2><p>Baza przechowuje metadane publicznych materiałów: źródło, datę, odnośnik, sposób pozyskania i opis niezbędny do pokazania kontekstu. X i YouTube są używane wyłącznie przez ich oficjalne interfejsy i w dozwolonym zakresie. W Klinice spinu publiczne posty polityków z X — treść, autor, data i link — trafiają do Groq (wstępna selekcja) i do Anthropic (diagnoza z wyszukiwaniem w sieci). Do tych usług nie przekazujemy danych czytelników: kont, reakcji ani komentarzy.</p></section>
    <section><h2>Cookies i bezpieczeństwo</h2><p>Serwis może używać technicznych cookies lub mechanizmów sesji koniecznych do logowania i ochrony formularzy. Nie uruchamiamy reklamowego śledzenia użytkowników. Końcowa konfiguracja przed startem wskaże dokładne kategorie i czas działania mechanizmów.</p></section>
    <section><h2>Twoje prawa i kontakt</h2><p>Możesz uzyskać dostęp do swoich danych, sprostować je, usunąć konto lub zgłosić sprzeciw — napisz na <a href="mailto:admin@spin.clinic">admin@spin.clinic</a>. Przysługuje Ci też skarga do Prezesa Urzędu Ochrony Danych Osobowych. Ta strona nie zastępuje końcowej informacji prawnej.</p></section>
  </InfoPage>;
}
