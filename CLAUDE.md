# Zasady projektu (spin.clinic, przeszłość.today, zbudujmi)

## Zasada nadrzędna: triaż każdego zadania (właściciel 5.10)
Przed każdym zadaniem zdecyduj i powiedz krótko, którą drogę wybierasz:
- **A. Odpal istniejące pętle** (research, Prawnik, design, budowa, strażnicy, wdrożenie) - na chwilę, tylko te potrzebne.
- **B. Zbuduj nową pętlę agentów** - gdy zadanie powtarza się albo wymaga stałej opieki; od razu z opiekunami i wpisem w LOOPS Automatyka.
- **C. Zrób sam** - gdy zadanie jest proste (mała poprawka, jedna odpowiedź) i pętla nic by nie dodała.
Przy A i B zbierz kilka niezależnych głosów (quasi-konsylium) i dopiero z ich werdyktu buduj.

## Design: zasady nadrzędne (właściciel; stosuj ZAWSZE, w każdym nowym boksie, stronie, raporcie i artefakcie)

Przed oddaniem czegokolwiek z boksami sprawdź każdy punkt:

1. **Dociąganie w boksie:** górny element przy górnej krawędzi, dolny element (odnośnik, data, źródło, kropki, przycisk)
   przy dolnej krawędzi; środek wypełnia resztę (`grid-template-rows: auto 1fr auto` albo flex z `margin-top: auto`).
2. **Równe boksy:** boksy jednego rodzaju w rzędzie mają tę samą, stałą wysokość (mierzoną na najdłuższym przypadku),
   a te same elementy stoją w każdym boksie na tej samej wysokości (tytuł, opis, liczby, stopka).
3. **Wspólne linie:** podpisy, liczby i odnośniki z sąsiednich kolumn stoją w jednej linii (np. podpisy liczb z datami wykresu,
   odnośniki na dole obu kolumn). Linie i krawędzie wyrównane do tych samych marginesów; nic nie wystaje z jednej strony.
4. **Tytuły w boksach w jednej linii:** mniejsza czcionka albo krótszy tekst zamiast łamania; opis o stałej liczbie linii.
5. **Stałe strefy ekranu:** przy zmianie widoku nic nie skacze; nagłówek, scena i komentarze mają stałe miejsca.
6. **Odstępy:** boksy jeden pod drugim nie stykają się krawędziami (stały odstęp); te same odstępy w całym widoku.
   Pierwszy element strony stoi blisko paska menu: najwyżej ok. 40 px na komputerze i 28 px na telefonie (właściciel 7.10).
7. **Etykiety stanu** (dobrze, do poprawy, BETA): małe, po prawej od tytułu, mniejsze niż tytuł.
8. **Styl:** czysto, minimalistycznie, najwyżej 2 kroje; raporty dla właściciela w ciemnym motywie spin.clinic.
9. **Sprawdzenie:** zrzut ekranu 1440 i 390 px przed oddaniem; zmierz położenia (górne i dolne krawędzie) zamiast zgadywać.
10. **Równe odstępy na granicach tła: odstęp od ostatniego widocznego elementu sekcji do krawędzi, gdzie zmienia się tło, musi być równy odstępowi od tej krawędzi do pierwszego widocznego elementu następnej sekcji - w każdej kolumnie osobno; sekcje na tym samym tle mają jeden rytm. Mierz: node C:\Users\User\zbudujmi\gust\odstepy.js <plik> 1440 (i 390) - wynik bez ZLE przed oddaniem.** (właściciel 8.10)

## Biblia designu: Laws of UX (lawsofux.com, właściciel 5.10)
Wszystkie 30 praw z zastosowaniem u nas: backend/news/laws_of_ux.py (LAWS). Każda poprawka designu wskazuje prawo, które naprawia.
Najczęściej u nas: Jakob (konwencje), Hick i Choice Overload (mniej wyborów), Fitts (cele 44 px), Proximity i Common Region (grupy),
Similarity (jeden styl dla jednej funkcji), Doherty (odpowiedź poniżej 400 ms), Peak-End (szczyt i zakończenie), Von Restorff (jedno wyróżnienie),
Tesler (złożoność bierze system, nie użytkownik). Projektant co tydzień sprawdza lawsofux.com i zgłasza nowe prawa lub zmiany.

## Pętla designu (obowiązkowa przed oddaniem strony, widoku, raportu lub artefaktu)
1. Projekt według przewodnika Projektanta (backend/news/projektant.py: GUIDE i CANON) i listy kontrolnej wyżej.
2. Zrzuty 1440 i 390 px oraz pomiar położeń.
3. Panel designu: niezależni recenzenci (UX/wygląd, czytelnik-laik, ruch i dostępność) oceniają zrzuty i dają konkretne poprawki.
4. Poprawki, ponowny pomiar; dopiero potem publikacja. Uwagi właściciela wracają do przewodnika jako nowe zasady.

## Mapa pętli do zadań (właściciel 5.10: „korzystaj z pętli zamiast robić sam”)
Każde zadanie właściciela przepuszczaj przez pętle w tej kolejności (Claude jest dyrygentem pracy w sesji):
1. Research: agenci badawczy w sesji (konkurencja, ceny, wzorce) + zbiór źródeł Badacza (backend/news/badacz.py).
2. Prawnik: twierdzenia publiczne, ceny porównawcze, dane osobowe (zasady w backend/news/pracownia_osint.py: LEGAL).
3. Design: przewodnik Projektanta + panel designu (UX, laik, dostępność) przed i po budowie.
4. Budowa: Codex (gdy ma limit; zlecenia małe i średnie) albo Claude; testy.
5. Strażnicy: Recenzent (teksty), panel designu (zrzuty i pomiar), testy, bezpieczeństwo.
6. Wdrożenie: komenda dla właściciela; potem opiekunowie pętli i Automatyk przejmują nadzór.
Hierarchię limitów pilnuje Dyrygent (backend/news/dyrygent.py): treść > strażnicy > niezawodność > rozwój > nauka.

## Język i komunikacja
- Z właścicielem po polsku, tylko krótki myślnik „-”, dwukropek przed wyliczeniem, bez powtórzeń.
- Przeglądy, plany i stan pokazuj graficznie (artefakt), z przełącznikiem „przed / po”, gdy coś się zmienia.
