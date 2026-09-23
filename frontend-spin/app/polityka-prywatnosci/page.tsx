export const metadata = { title: 'Prywatność i cookies · spin.clinic' };

export default function PrivacyPage() {
  return <article className="mvp-info-page">
    <header className="mvp-info-hero"><p>INFORMACJE</p><h1>Prywatność i cookies</h1><p>To robocza informacja dla pilotażu. Przed publicznym uruchomieniem uzupełnimy ją o dane administratora, kanał kontaktu, okresy przechowywania i aktualną listę dostawców.</p></header>
    <section><h2>Jakie dane mogą pojawić się w serwisie</h2><p>Bez logowania strona zapisuje tylko ustawienia potrzebne do działania interfejsu na danym urządzeniu, na przykład wybrany motyw. Po udostępnieniu kont użytkownik może podać nazwę użytkownika, opcjonalny adres e-mail i hasło; hasło jest przechowywane wyłącznie w postaci zabezpieczonego skrótu. Konto może zapisywać ulubione materiały, prywatne nitki kontekstowe, reakcje, komentarze i zgłoszenia.</p></section>
    <section><h2>Po co je przetwarzamy</h2><p>Dane konta służą do zalogowania, ochrony przed nadużyciami i działania funkcji wybranych przez użytkownika. Komentarze oraz zgłoszenia służą moderacji. Prywatne nitki nie są publiczne ani nie są przekazywane modelom AI jako materiał do analizy.</p></section>
    <section><h2>Materiały ze źródeł i zewnętrzne usługi</h2><p>Baza przechowuje metadane publicznych materiałów: źródło, datę, odnośnik, sposób pozyskania i opis niezbędny do pokazania kontekstu. X i YouTube są używane wyłącznie przez ich oficjalne interfejsy i w dozwolonym zakresie. NVIDIA NIM i Groq pozostają wyłączone do czasu osobnego pilotażu; jeśli zostaną włączone, do usługi może trafić wyłącznie krótki, dopuszczony fragment publicznego materiału wraz ze źródłem i datą.</p></section>
    <section><h2>Cookies i bezpieczeństwo</h2><p>Serwis może używać technicznych cookies lub mechanizmów sesji koniecznych do logowania i ochrony formularzy. Nie uruchamiamy reklamowego śledzenia użytkowników. Końcowa konfiguracja przed startem wskaże dokładne kategorie i czas działania mechanizmów.</p></section>
    <section><h2>Twoje prawa i kontakt</h2><p>Przed startem opublikujemy dane administratora i adres do spraw prywatności. Wtedy będzie można uzyskać dostęp do danych, sprostować je, usunąć konto lub zgłosić zastrzeżenie zgodnie z obowiązującymi zasadami. Ta strona nie zastępuje końcowej informacji prawnej.</p></section>
  </article>;
}
