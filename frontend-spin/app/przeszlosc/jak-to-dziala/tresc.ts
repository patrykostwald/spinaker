/**
 * Treść strony "Jak to działa" (przeszłość.today, seria PWA + "Jak to działa", 13.10.2026).
 * Każde zdanie pochodzi z istniejących materiałów repo (źródło w komentarzu przy bloku). Czego nie dało się potwierdzić w kodzie,
 * jest oznaczone "do potwierdzenia" (pole tbc) i trafia na listę do prawnika w gust\spin\port\etap-port-fe-pwa.md.
 * Brak twardych liczb, których nie ma w kodzie; "brak w naszych danych" zawsze z zakresem i datą.
 */
export const AKTUALIZACJA = '13 października 2026';
export const KONTAKT = 'kontakt@iapply.pl';

/** Twarde spacje: jednoliterowe słowa (a, i, o, u, w, z) oraz liczby nie zostają na końcu wiersza. */
export const nb = (text: string) => text
  .replace(/(?<![^\s(„"])([aiouwzAIOUWZ])\s+/g, '$1 ')
  .replace(/(\d)\s+(?=[^\s])/g, '$1 ');

export type Sekcja = { id: string; numer: string; tytul: string };
/** Spis treści i kolejność sekcji: jedno źródło dla nagłówków, kotwic i spisu. */
export const SEKCJE: Sekcja[] = [
  { id: 'jak', numer: '01', tytul: 'Jak to działa' },
  { id: 'kroki', numer: '02', tytul: 'W trzech krokach' },
  { id: 'dane', numer: '03', tytul: 'Skąd mamy dane' },
  { id: 'laczenie', numer: '04', tytul: 'Jak łączymy osoby i podmioty' },
  { id: 'miara', numer: '05', tytul: 'Ta sama miara dla wszystkich' },
  { id: 'ai', numer: '06', tytul: 'Gdzie jest AI' },
  { id: 'braki', numer: '07', tytul: 'Czego tu nie ma i jak czytać braki' },
  { id: 'bledy', numer: '08', tytul: 'Błędy i sprostowania' },
  { id: 'redakcje', numer: '09', tytul: 'Dla dziennikarzy i badaczy' },
];

/** Zasada naczelna (właściciel 13.10, korekta landingu): jedno zdanie, to samo nad sekcją "Dane w jednym miejscu" w profilu osoby. */
export const ZASADA = 'To narzędzie pokazuje powiązane dane publiczne. Nie ocenia osób i nie wyciąga wniosków: wnioski należą do Ciebie. Powiązanie w danych nie jest zarzutem.';

export const OBIETNICA = 'Wpisz temat, osobę albo numer KRS, a pokażemy, kto o tym mówi, jak głosował Sejm i z kim jest związany: każdy fakt ze źródłem, które możesz sprawdzić.';

/** Kroki (TopicTree: sekcja „Jak to działa”, FEATURES w przeszlosc_dostep.py). */
export const KROKI = [
  { n: '1', tytul: 'Wpisz temat, osobę albo numer KRS', tekst: 'Wystarczy słowo, na przykład CPK, nazwisko posła albo numer KRS spółki. Tryb Temat, Osoba albo Spółka zawęża dopasowanie.' },
  { n: '2', tytul: 'Zobacz, kto mówi, jak głosował Sejm i z kim jest związany', tekst: 'Oś czasu wpisów, druków i artykułów, głosowania klubów i posłów oraz drzewo powiązań ze spółkami z KRS.' },
  { n: '3', tytul: 'Kliknij źródło i sprawdź oryginał', tekst: 'Każdy wiersz ma ślad źródła: domenę i odnośnik do oryginału. Możesz też zapisać kopię w archiwum i skopiować gotowy przypis.' },
];

/** Tabela źródeł. Odświeżanie = ustawienia zbieraczy (backend/scraper/public_records.py, Spec.refresh_hours); tbc = do potwierdzenia. */
export type Zrodlo = { nazwa: string; domena: string; zawiera: string; zakres: string; odswiezanie: string; ograniczenia: string; tbc?: string[] };
export const ZRODLA: Zrodlo[] = [
  { nazwa: 'Sejm', domena: 'api.sejm.gov.pl',
    zawiera: 'Posłowie, głosowania imienne, druki, interpelacje i zapytania, wystąpienia, konsultacje, procesy legislacyjne, komisje, transmisje wideo, indeks oświadczeń majątkowych.',
    zakres: 'Kadencja 10, od 13 listopada 2023.', odswiezanie: 'Od godziny (głosowania) do tygodnia (oświadczenia).',
    ograniczenia: 'To nie jest pełne archiwum głosowań Sejmu: pokazujemy to, co zaimportowaliśmy do bazy. Oświadczenia: tylko indeks, bez treści. Nieobecność nie jest głosem.' },
  { nazwa: 'KRS', domena: 'api-krs.ms.gov.pl',
    zawiera: 'Funkcje w zarządach i radach spółek i fundacji (z datami od i do), odpisy aktualne, zmiany w obserwowanych podmiotach.',
    zakres: 'Stan z rejestru na dzień pobrania odpisu.', odswiezanie: 'Zmiany: raz na dobę.',
    ograniczenia: 'Funkcja w KRS to kontekst osoby, nie dowód związku z tematem ani winy. Osoby pokazujemy tylko po potwierdzeniu w rejestrze osób publicznych.' },
  { nazwa: 'Zamówienia publiczne: TED', domena: 'ted.europa.eu',
    zawiera: 'Ogłoszenia zamawiających z Polski: wykonawca, wartość, klasyfikacja CPV.',
    zakres: 'Pierwsze zasilanie: ostatnie 12 miesięcy.', odswiezanie: 'Raz na dobę.',
    ograniczenia: 'Kwoty z ogłoszeń, nie z umów. Łączymy tylko po identyfikatorze wykonawcy (NIP, numer VAT).' },
  { nazwa: 'Zamówienia publiczne: BZP', domena: 'ezamowienia.gov.pl',
    zawiera: 'Ogłoszenia, w których podmiot jest zamawiającym (łączone po NIP zamawiającego).',
    zakres: 'Do potwierdzenia.', odswiezanie: 'Do potwierdzenia.',
    ograniczenia: 'Czy źródło jest włączone na produkcji: do potwierdzenia. Kwoty z ogłoszeń, nie z umów.', tbc: ['zakres', 'odswiezanie'] },
  { nazwa: 'Fundusze UE', domena: 'cohesiondata.ec.europa.eu, ec.europa.eu',
    zawiera: 'Projekty polityki spójności 2014-2020 w Polsce (Kohesio) oraz beneficjenci z Polski w budżecie UE zarządzanym przez Komisję (FTS).',
    zakres: 'FTS: od 2021 roku. Kohesio: 2014-2020.', odswiezanie: 'Kohesio: raz w tygodniu. FTS: raz na 30 dni.',
    ograniczenia: 'Licencje: Kohesio CC0, FTS CC BY 4.0. Rekordy dopasowane tylko po nazwie pokazujemy osobno jako niepowiązane i nie wliczamy do sum.' },
  { nazwa: 'Parlament Europejski', domena: 'howtheyvote.eu, integritywatch.eu',
    zawiera: 'Głosowania europosłów z Polski, deklaracje dochodów i spotkania z lobbystami; rejestr przejrzystości UE (podmioty z Polski); identyfikatory osób z Wikidata.',
    zakres: 'Europosłowie z Polski; okres: do potwierdzenia.', odswiezanie: 'Od raz na dobę do raz w tygodniu.',
    ograniczenia: 'Tytuły głosowań w oryginale (EN). Licencje: Integrity Watch EU ODbL, Wikidata CC0.', tbc: ['zakres'] },
  { nazwa: 'Lobbing', domena: 'gov.pl, sejm.gov.pl',
    zawiera: 'Rejestr lobbingu MSWiA i lobbing w Sejmie.',
    zakres: 'Do potwierdzenia.', odswiezanie: 'Raz w tygodniu.',
    ograniczenia: 'Strony za zabezpieczeniem przed botami pomijamy: nie obchodzimy go, więc źródło bywa wstrzymane.', tbc: ['zakres'] },
  { nazwa: 'Wpisy na X', domena: 'x.com',
    zawiera: 'Wpisy kont osób i instytucji publicznych, których konto potwierdziliśmy sprawdzonym dowodem.',
    zakres: 'Do potwierdzenia.', odswiezanie: 'Do potwierdzenia.',
    ograniczenia: 'Przy wpisie jest odnośnik do oryginału i kopia w archiwum, a po zmianie tekstu ostrzeżenie. Regulamin X i prawo cytatu: do potwierdzenia.', tbc: ['zakres', 'odswiezanie'] },
  { nazwa: 'Media', domena: 'redakcje (odnośniki)',
    zawiera: 'Tytuł, data i odnośnik do artykułu w redakcji. Treść czytasz u wydawcy.',
    zakres: 'Do potwierdzenia.', odswiezanie: 'Do potwierdzenia.',
    ograniczenia: 'Dopasowanie do osoby lub tematu bywa automatyczne (nazwisko, słowa tematu), oznaczone „automatyczne”; możliwe pomyłki.', tbc: ['zakres', 'odswiezanie'] },
  { nazwa: 'Kilometrówki i biura posłów', domena: 'jakglosuja.pl, orka.sejm.gov.pl',
    zawiera: 'Rozliczenia przejazdów i biur poselskich, sprawdzone z listą posłów Sejmu.',
    zakres: 'Do potwierdzenia.', odswiezanie: 'Raz na 30 dni.',
    ograniczenia: 'jakglosuja.pl to serwis zewnętrzny, nie rejestr urzędowy. PDF Kancelarii Sejmu niedostępne automatycznie.', tbc: ['zakres'] },
  { nazwa: 'spin.clinic', domena: 'spin.clinic',
    zawiera: 'Diagnozy wpisów polityków: ocena technik perswazji w skali 0-100 (Dr. Spin, AI).',
    zakres: 'Wpisy kont, które mamy w serwisie.', odswiezanie: 'Do potwierdzenia.',
    ograniczenia: 'To ocena AI, nie ustalenie faktów. Warstwa „Wpływ na narrację” jest domyślnie wyłączona.', tbc: ['odswiezanie'] },
  { nazwa: 'Inne źródła', domena: 'pkw.gov.pl, archiwum reklam Meta',
    zawiera: 'Finanse partii i komitetów (PKW) oraz archiwum reklam politycznych Meta do 5 października 2025.',
    zakres: 'Reklamy: do 5 października 2025.', odswiezanie: 'PKW: raz w tygodniu.',
    ograniczenia: 'Zbieramy je, ale gdzie dokładnie są widoczne w serwisie: do potwierdzenia.', tbc: ['ograniczenia'] },
];
export const ZRODLA_UWAGA = `Interwały to ustawienia zbieraczy w kodzie serwisu. Faktyczny harmonogram na produkcji i datę ostatniej aktualizacji każdego źródła: brak w naszych danych (stan na ${AKTUALIZACJA}). Datę pobrania danych źródłowych każdego wiersza podaje kolumna data_pobrania w eksporcie.`;

/** Łączenie (przeszlosc_osoba.py, przeszlosc.py, drzewo_pieniedzy.py, przeszlosc_v3.py). Listy od najkrótszej do najdłuższej. */
export const LACZENIE = [
  'Konta X: tylko po sprawdzonym dowodzie, że konto należy do osoby.',
  'Spółki i fundacje: po numerach KRS, NIP i REGON, nigdy po samej nazwie.',
  'Posłowie z dokumentami i głosowaniami: wyłącznie po oficjalnym identyfikatorze Sejmu.',
];
export const LACZENIE_WZMIANKI = 'Wyjątek stanowią wzmianki w artykułach: to automatyczne dopasowanie po nazwisku albo słowach tematu. Oznaczamy je jako „automatyczne” i nie traktujemy jak powiązania. Potwierdzone materiały medialne to osobna lista.';
export const LACZENIE_ZNACZENIE = [
  'Każda pozycja prowadzi do źródła, więc możesz sprawdzić powiązanie sam.',
  'Współwystępowanie oznacza wspólny dokument albo temat w źródle; nie jest dowodem współpracy.',
  'Funkcja w KRS to kontekst osoby, nie dowód związku z tematem ani winy.',
  'Linia ciągła oznacza powiązanie udokumentowane w źródle, linia kreskowana kontekst z KRS.',
];
export const LACZENIE_NIE = [
  'Nie oznacza zarzutu, winy ani oceny politycznej.',
  'Nie wynika z samej zgodności nazwisk ani nazw.',
  'Kwoty z ogłoszeń nie są kwotami z umów.',
];
export const SCIEZKI = [
  ['Poseł', 'identyfikator Sejmu', 'głosowanie albo druk', 'sejm.gov.pl'],
  ['Spółka', 'numer KRS lub NIP', 'ogłoszenie TED, projekt UE', 'ted.europa.eu, kohesio'],
];

/** Odstępstwa od klubu: backend/news/voting_anomalies.py (METHOD, THRESHOLDS). */
export const PROGI: [string, string][] = [
  ['Okno', 'Domyślnie ostatnie 90 dni, z przełącznikiem na całą kadencję.'],
  ['Liczymy', 'Oddane głosy: za, przeciw, wstrzymał się. Nieobecność i głos na liście nie są odstępstwem.'],
  ['Większość klubu', 'Najczęstszy głos posłów klubu w danym głosowaniu. Remis albo mniej niż 3 oddane głosy klubu: głosowanie pomijamy.'],
  ['Wyższy udział', 'Poseł, u którego udział głosów innych niż większość klubu jest wyższy od mediany klubu o więcej niż 5 punktów procentowych (posłowie z co najmniej 20 głosami).'],
  ['Głos inny niż większość klubu przy zgodności klubu', 'Głos inny niż większość klubu w głosowaniu, w którym co najmniej 80% oddanych głosów klubu było takich samych.'],
];

export const MIARA = [
  'Rządzący i opozycja przechodzą przez identyczne zapytania i te same reguły.',
  'Obóz (rządzący, opozycja, instytucja) podajemy słowem, bez kolorów.',
  'Progi są jedne dla każdego klubu; głos inny niż większość klubu wynika z definicji, nie jest zarzutem.',
];

export const AI_PUNKTY = [
  'Diagnozy pochodzą ze spin.clinic: Dr. Spin (AI) ocenia techniki perswazji we wpisach, od 0 do 100, tą samą miarą dla wszystkich.',
  'To ocena AI, nie ustalenie faktów. Siła spinu to nasilenie technik perswazji w jednym wpisie, nie procent fałszu i nie miara winy.',
  'Diagnozy są domyślnie ukryte: pokazuje je przełącznik „Wpływ na narrację” w pasku. Możesz go wyłączyć w każdej chwili.',
  'Podsumowania („Policzone z listy, bez AI”) i odstępstwa od klubu liczymy regułami z kodu, bez AI.',
  'Tematy dnia wybiera automat z danych (przedmioty druków i skróty z wpisów), nie AI.',
  'Typ artykułu (komunikat, wywiad, komentarz) jest oszacowany automatycznie i tak oznaczony.',
];

/** Braki (zasady: Poprawki.tsx, GlosowaniaPage.tsx, przeszlosc_eksport.py, przeszlosc_v3.py). Od najkrótszej do najdłuższej. */
export const BRAKI = [
  'Nieobecność nie jest głosem.',
  'Tylko osoby i podmioty publiczne, bez osób prywatnych.',
  'Wynik nieustalony: brak w naszych danych wymaganej większości w głosowaniu (np. przy listach).',
  'Zakres jest ograniczony: nie obejmuje wszystkich osób, spółek ani wypowiedzi, więc brak wyniku nie oznacza braku powiązania.',
  'Eksport ma limit techniczny 20 000 wierszy na kategorię; po przekroczeniu w pliku jest wiersz „pominięto N”.',
  'Gdy czegoś nie mamy, piszemy „brak w naszych danych” z zakresem i datą, a nie samo „brak”. Przykład: głosowania z filtrem, który nic nie zwrócił, podają zakres i datę ostatniego głosowania w bazie.',
];
export const BRAKI_NIE_MAMY = 'Czego nie mamy dziś w bazie (wg katalogu źródeł z 8 października 2026): Centralnego Rejestru Umów, rejestru beneficjentów rzeczywistych, ksiąg wieczystych i orzeczeń sądów.';

/** Błędy i sprostowania (Sprostowanie.tsx, Poprawki.tsx, przeszlosc_wersja.py). */
export const BLEDY_KROKI = [
  'Przy profilu osoby, spółce i w drzewie powiązań kliknij „Zgłoś błąd lub sprostowanie”.',
  'Napisz, co jest nieprawdziwe, i podaj źródło, jeśli je masz. E-mail jest nieobowiązkowy: podaj go, jeśli chcesz odpowiedź.',
  'Zgłoszenie trafia do zespołu razem z identyfikatorem rekordu. Poprawki sprawdzamy z podanym źródłem.',
  'Przyjęte i wprowadzone sprostowania widać w publicznym rejestrze poprawek: data, rekord i nazwa, bez treści zgłoszenia i bez danych zgłaszającego.',
];

/** Dla dziennikarzy i badaczy (przeszlosc_eksport.py, przeszlosc_osoba.py, PersonProfile.tsx, FEATURES). */
export const REDAKCJE = [
  'Kanał RSS tematu: bez konta, w czytniku RSS albo w narzędziu redakcji.',
  'Gotowy przypis: cytat z autorem, datą i źródłem do wklejenia w tekst.',
  'Eksport CSV i JSON profilu osoby, spółki i tematu, z odnośnikiem do oryginału przy każdym wierszu.',
  'CSV tematu ma kolumny: data, rodzaj, treść, autor, strona, źródło, link, a na końcu źródło i datę pobrania.',
  'CSV profilu osoby i spółki ma kolumny: data, rodzaj, tresc, spin, link, zrodlo, data_pobrania, pewnosc_powiazania, identyfikator. Separator średnik, UTF-8 z BOM, na końcu przypis do cytowania.',
];
export const PRZYPIS = 'przeszłość.today, profil osoby publicznej „Imię Nazwisko”, dane z rejestrów publicznych (źródła i licencje przy każdym wierszu), pobrano RRRR-MM-DD, adres profilu.';
