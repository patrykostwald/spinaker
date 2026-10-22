# Zasady projektu „spin.clinic social”

Źródła: decyzje właściciela 3.10.2026 oraz werdykty Konsylium z 3.10 (część społecznościowa, strona główna i limity,
porównanie z X / Threads / Bluesky). Obowiązują przy każdej zmianie nitek, osi, komentarzy i panelu użytkownika.
Kolory i fonty zostają z naszego systemu (`packages/ui/src/kit/kit.css`, tokeny `--sc-*`); propozycje Konsylium innych palet
(np. czysta czerń, kolory Apple) odrzucone, żeby serwis był jednym systemem.

## Dziesięć zasad
1. **Czysto i minimalistycznie**: kolor zamiast opisanych liczb; tytuły i etykiety tylko tam, gdzie bez nich nie da się zrozumieć.
2. **Oś = strumień kart** oddzielonych cienką linią (hairline w kolorze `--sc-line`), bez cieni; odstęp wewnętrzny 16 px.
3. **Nitka = poziomy pasek**: boksy ok. 240 px szerokości, przewijanie z przyciąganiem (scroll-snap), z prawej widać 16 px
   kolejnego boksu i delikatną maskę gradientową (wiadomo, że jest więcej, bez strzałek).
4. **Rozwinięcie nitki w miejscu**: boksy rozsuwają się w poziomie, między nimi na „sznurku” powiązania; animacja ok. 300 ms
   (`cubic-bezier(.2,.8,.2,1)`, transform/opacity), przy ograniczonych animacjach bez ruchu.
5. **Ocena trzema ikonami ✓ ? ✕** (zielony / żółty / czerwony z tokenów), narysowanymi tą samą kreską co ramka nitki, w trzech
   przerwach dolnej krawędzi ramki (lewo, środek, prawo); bez liczb w ramce; intensywność koloru rośnie z udziałem głosów,
   bez głosów szare; liczby w podpowiedzi (najechanie / długie dotknięcie) i w `aria-label`. Boksy nie mają ocen.
6. **Akcje pod nitką: najwyżej 4** (Oceń, Komentarz, Udostępnij przez natywne udostępnianie, Zapisz), odstęp 24 px, bez liczb
   w UI poza podpowiedziami; liczba komentarzy jako ikona dymka w rogu paska.
7. **Komentarze płaskie** pod nitką: awatar 24 px (inicjał), nick, czas, tekst, akcje; odwołanie `@boks N` jako mały chip,
   kliknięcie przewija tor do boksu i podświetla go na 1,5 s.
8. **Typografia i siatka**: treść 15 px / 1.5, metadane 13 px w kolorze pomocniczym, tytuły 15-16 px / 600; siatka 4 px;
   promienie 8 px; kontrast co najmniej WCAG AA.
9. **Kolor w tekście subtelny i znaczący**: kolor coś oznacza (nie ozdoba), maks. 2 kolory w bloku tekstu, przygaszone barwy na
   ciemnym tle, zieleń i czerwień nigdy obok siebie bez kształtu ✓ / ✕, linki i przyciski bez koloru tekstu (podkreślenie / ramka).
10. **Stany**: ładowanie jako szkielety (szare prostokąty w kształcie treści), odświeżanie natywne przeglądarki, puste stany
    to ikona i jedno zdanie (+ jeden przycisk tylko tam, gdzie prowadzi do pierwszego kroku).

## Limity znaków
Tytuł nitki 80, komentarz autora w boksie 400, powiązanie 200, komentarz pod nitką 600. W widoku 3 linie + „Rozwiń” w miejscu.
Dr. Spin pisze w tych samych limitach.

## Nawigacja
Telefon (aplikacja): dolny pasek 5 pozycji: Start, Nitki, Szukaj, Powiadomienia, Profil (badge z liczbą na dzwonku).
Komputer (od 768 px): te same pozycje w menu bocznym z etykietami. Klinika (przekazy, wywiady, diagnozy) w menu górnym / Start.

## Strona główna
Krótki nagłówek „Jak działa przekaz” z rozwijanym „Czym jest spin?”, pod nim jedna rozwinięta nitka „Spin dnia” Dr. Spina,
dalej oś nitek (pasek za paskiem). Wiadomości, Twoje wiadomości i Baza nie stoją na głównej.
