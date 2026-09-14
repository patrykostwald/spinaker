# Osobny produkt archiwalny dla dziennikarzy

## Decyzja architektoniczna

Nie tworzymy drugiej fizycznej kopii bazy jako źródła prawdy. `spin.clinic` i przyszły produkt zawodowy korzystają z jednego kanonicznego rejestru źródeł, materiałów, wersji, relacji i pochodzenia danych. Osobny interfejs otrzymuje własną domenę, markę, API oraz ściśle ograniczony widok danych.

Kopie bezpieczeństwa całej bazy pozostają niezależnym obowiązkiem operacyjnym. Nie są osobnym produktem ani miejscem, do którego aplikacje zapisują równolegle.

## Propozycja produktu

Robocza nazwa: **Archiwum kontekstu**. Pierwsza domena do testu: `przeszlosc.today`. `drewniej.pl` może służyć jako kampanijny adres lub projekt historyczny, ale brzmi mniej neutralnie jako codzienne narzędzie redakcyjne. Nazwę i domenę potwierdzimy badaniem z kilkoma dziennikarzami przed publicznym uruchomieniem.

Produkt pokazuje:

- boxy z tytułem, typem materiału, autorem, wydawcą, oryginalnym URL, datą publikacji i czasem pobrania;
- indeks według źródła, daty, osoby, organizacji, tematu i typu materiału;
- chronologię oraz jawne relacje między materiałami;
- zakres pokrycia, braki danych, korekty i historię wersji;
- zapisane wyszukiwania, alerty i eksport w dozwolonym zakresie;
- opcjonalne narzędzia AI do wyszukiwania i porządkowania, zawsze z identyfikatorami dowodów.

Produkt nie pokazuje komentarzy, reakcji, profili społecznościowych, Dr Spina ani redakcyjnych etykiet spin.clinic. Nie sprzedajemy cudzych pełnych tekstów. Oferta obejmuje dostęp do uporządkowanych metadanych, pochodzenia, relacji, chronologii, narzędzi pracy i własnych analiz, w zakresie dozwolonym dla danego źródła.

## Rozdzielenie techniczne

1. Jeden magazyn ingestu i jeden identyfikator każdego materiału.
2. Warstwa praw określa osobno możliwość przechowywania, indeksowania, publicznego pokazania, eksportu i użycia w AI.
3. Publiczne API zawodowego produktu zwraca wyłącznie pola z allowlisty i nie łączy tabel aktywności użytkowników.
4. Oddzielna aplikacja lub wariant hosta korzysta ze wspólnego design systemu, ale ma własną nawigację i analitykę produktu.
5. Konta mogą później działać wspólnie przez jedno uwierzytelnianie, przy osobnych rolach i subskrypcjach.
6. Cache lub indeks wyszukiwawczy może mieć osobną, odbudowywalną kopię zoptymalizowaną pod zapytania. Nie staje się drugim źródłem prawdy.

## Kolejność

- MVP spin.clinic: nie rozszerzać zakresu premiery o drugi pełny frontend.
- Równolegle: utrzymać neutralny model danych, pochodzenie, prawa użycia i eksport, aby wydzielenie produktu nie wymagało migracji całej bazy.
- Po stabilizacji ingestu: przygotować klikalny prototyp oraz rozmowy z 5–10 dziennikarzami i researcherami.
- Następnie: prywatna beta z wyszukiwaniem, osią czasu, alertami i eksportem; bez społeczności i Dr Spina.
- Dopiero po pomiarze użycia: płatne zespoły, API, raporty i integracje redakcyjne.

## Kryteria powodzenia pilota

- czas znalezienia źródła lub chronologii krótszy niż przy ręcznym wyszukiwaniu;
- wynik zawsze pokazuje pochodzenie i rzeczywisty zakres pokrycia;
- brak ujawnienia komentarzy, reakcji i prywatnych danych spin.clinic;
- eksport respektuje decyzję praw dla każdego pola i źródła;
- użytkownicy wracają do zapisanych wyszukiwań i alertów;
- co najmniej kilku testerów deklaruje gotowość zapłaty za dostęp zespołowy.
