# Identyfikacja i szaty graficzne spin.clinic

Stan decyzji na 14 września 2026.

## Identyfikacja domyślna

Główna szata ma być najciemniejsza: głęboki grafit bliski czerni, złamana biel oraz oszczędny chłodny miętowy akcent. Portal pozostaje minimalistyczny i spokojny mimo dużej liczby tytułów. Ruch przewijanych nitek, odstęp, typografia i wyrównanie rozdzielają informacje częściej niż ramki.

Ostateczny wariant główny wybieramy przed wdrożeniem całej identyfikacji. Wersja domyślna jest również wyglądem dla użytkownika niezalogowanego oraz podstawą materiałów udostępnianych poza portalem.

## Znak

Znak składa się z czterech liter czytanych zgodnie z ruchem wskazówek zegara:

- `S` — góra,
- `P` — prawa strona,
- `I` — dół,
- `N` — lewa strona.

Środek pozostaje pusty. Ruch mogą zaznaczać najwyżej cztery bardzo drobne punkty; bez pełnego okręgu i bez dosłownego krzyża medycznego. Znak ma działać jako favicon, avatar na X oraz element pełnego logotypu `spin.clinic`. Skojarzenie z diagnostyką jest pożądane, ale znak nie może udawać placówki medycznej.

## Typografia

Rekomendowana jest jedna spójna superrodzina IBM Plex:

- IBM Plex Sans — nawigacja, wyszukiwarka, treść interfejsu, komentarze i większość tytułów boxów,
- IBM Plex Serif — tytuły ważnych nitek, wyróżnione analizy i cytaty Dr Spin,
- IBM Plex Mono — źródła, czas, daty, liczby, identyfikatory i ślad dowodowy.

Na telefonie pozostają te same kroje. Zmieniamy skalę, szerokość wiersza i odstępy, dzięki czemu marka pozostaje rozpoznawalna. Nie zmniejszamy podstawowego tekstu tylko po to, aby zmieścić więcej boxów.

## Trzy szaty użytkownika

Zarejestrowany użytkownik może wybrać jedną z trzech kompletnych szat. MVP przygotowuje architekturę tokenów, a wybór w profilu może zostać udostępniony razem z personalizacją konta.

1. **Clinical Dark** — domyślna; grafit, złamana biel, chłodna mięta.
2. **Civic Ink** — ciemny atramentowy granat, papierowa biel, mineralny błękit.
3. **Light Archive** — jasne, ciepłe tło przypominające papier, ciemny atrament i ten sam miętowy kolor funkcjonalny.

Szata nie zmienia znaczenia informacji. Kolory ocen, ostrzeżeń, sponsorowania i statusów weryfikacji muszą zachowywać ten sam sens i odpowiedni kontrast. Ustawienie jest przypisane do profilu, a przed zalogowaniem może być zachowane lokalnie w urządzeniu. System respektuje `prefers-color-scheme`, `prefers-reduced-motion` i ustawienia kontrastu.

## Stały układ głównej

Niezależnie od szaty zachowujemy kolejność:

1. Wszystkie wiadomości,
2. TOP 10,
3. Top temat dnia,
4. jedna nitka Dr Spin, wyjątkowo dwie,
5. jedna jawnie oznaczona nitka sponsorowana,
6. nitki autoryzowanych dziennikarzy.

Nitka wydarzenia może mieć duży punkt wyjścia po lewej oraz chronologiczny, przewijany pasek powiązanych boxów po prawej.
