# Zasady projektu (spin.clinic, przeszłość.today)

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
7. **Etykiety stanu** (dobrze, do poprawy, BETA): małe, po prawej od tytułu, mniejsze niż tytuł.
8. **Styl:** czysto, minimalistycznie, najwyżej 2 kroje; raporty dla właściciela w ciemnym motywie spin.clinic.
9. **Sprawdzenie:** zrzut ekranu 1440 i 390 px przed oddaniem; zmierz położenia (górne i dolne krawędzie) zamiast zgadywać.

## Język i komunikacja
- Z właścicielem po polsku, tylko krótki myślnik „-”, dwukropek przed wyliczeniem, bez powtórzeń.
- Przeglądy, plany i stan pokazuj graficznie (artefakt), z przełącznikiem „przed / po”, gdy coś się zmienia.
