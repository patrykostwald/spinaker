# WERSJA ROBOCZA - przykład „Tygodnika legislacyjnego” (branża: finanse, podatki, żywność)

Status: szkic do testu popytu, nie do wysyłki. Dane: publiczne strony Rządowego Procesu Legislacyjnego (kopie z 8-9.09.2026
zapisane w repozytorium: `backend/scraper/fixtures/rcl/`). Przed publikacją każdy wpis trzeba sprawdzić na żywej stronie RCL
(stan mógł się zmienić) - [DP]. Streszczenia treści oznaczone „[do uzupełnienia]” powstaną dopiero z pobranych dokumentów;
nic nie dopisujemy z głowy.

---

## Tygodnik legislacyjny - Finanse i podatki
**Tydzień 2-8 września 2026** · 4 projekty w ruchu · 1 nowe zgłoszenie lobbingowe [przykład syntetyczny]

### Najważniejsze w 30 sekund
1. **PIT i CIT (UD447)** - projekt zmian w podatkach dochodowych, wnioskodawca: Minister Finansów i Gospodarki;
   utworzony 13.08, zmieniony 08.09. Co to znaczy dla firmy: [do uzupełnienia z uzasadnienia i OSR].
2. **Ustawa okołobudżetowa na 2026 (UD463)** - skierowana do Sejmu (etap 14), dalsze prace na stronach Sejmu.
3. **Rynek finansowy (UC132)** - pakiet zmian „w celu rozwoju rynku finansowego oraz zwiększenia stabilności”; zmieniony 08.09.
4. **Bezpieczeństwo żywności (UD 247)** - zmiany w ustawie o bezpieczeństwie żywności i o Państwowej Inspekcji Sanitarnej;
   zmieniony 08.09 (ważne dla producentów i sieci handlowych).

### Tabela zmian w tygodniu
| Projekt | Nr wykazu | Wnioskodawca | Etap teraz | Zmiana w tygodniu | Termin uwag |
|---|---|---|---|---|---|
| Zmiana ustawy o PIT i CIT | UD447 | MFiG | [DP] | aktualizacja 08.09 | [DP] |
| Szczególne rozwiązania - budżet 2026 | UD463 | MFiG | Skierowanie do Sejmu | Rada Ministrów 01.09, do Sejmu 02.09 | - |
| Rozwój rynku finansowego | UC132 | MF | [DP] | aktualizacja 08.09 | [DP] |
| Bezpieczeństwo żywności i PIS | UD 247 | MZ | [DP] | aktualizacja 08.09 | [DP] |

### Kto się zgłosił (lobbing i konsultacje)
- [przykład syntetyczny] 2 zgłoszenia zainteresowania pracami (organizacja pozarządowa, izba gospodarcza) - w prawdziwym
  wydaniu: nazwy podmiotów z publicznego rejestru RCL, bez danych osób.
- Uwagi z konsultacji: liczba stanowisk i 1 zdanie o głównym sporze z każdego [do uzupełnienia].

### Kalendarz na następny tydzień
- Komisja Prawnicza, posiedzenia komitetów RM, końce terminów konsultacji - z zaproszeń publikowanych przez RCL [DP].

### Co zrobić
- Jeśli projekt dotyczy Twojej firmy: termin uwag, link do formularza „Wyślij komentarz do projektu” na stronie RCL.
- Pełna lista projektów w branży: panel (link w wersji płatnej).

---
Źródło: Rządowe Centrum Legislacji, legislacja.rcl.gov.pl (link do każdego projektu, data pobrania przy każdym wpisie).
Dane ujednolicone i uporządkowane przez iapply sp. z o.o. (operatora spin.clinic i przeszłość.today); treść pism
i dokumentów należy do RCL i organów wnioskujących. To przegląd informacyjny, nie porada prawna.

## Jak to powstaje (automatycznie, ok. 0 godzin właściciela tygodniowo [szacunek])
1. Noc (01-06, 1 zapytanie / 5 s): `rcl_harvest` pobiera zmiany projektów i katalogów (gotowe w repozytorium).
2. Rano: przypisanie do branż po „Działach” i „Hasłach” RCL + słowa kluczowe klienta; streszczenie „co to znaczy dla firmy”
   przez model w PCSS (koszt ok. grosze na wydanie [szacunek]: ok. 200 tys. tokenów x 0,61 zł / 1 mln).
3. Kontrola: drugi model sprawdza, czy streszczenie nie twierdzi niczego spoza dokumentu („nie wiem” zamiast zgadywania).
4. Wysyłka mailem w poniedziałek 7:00 + panel z filtrem (API `news.rcl_api` już istnieje).
