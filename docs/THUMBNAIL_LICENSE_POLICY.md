# Miniatury i obrazy: zasada MVP

Każdy obraz jest osobnym utworem. Zgoda na pobieranie metadanych albo tekstu
nie jest automatycznie zgodą na skopiowanie zdjęcia, zrobienie jego miniatury
ani pokazanie go w portalu.

## Stan domyślny

Box otrzymuje własną ikonę rodzaju materiału albo źródła. Nie pobieramy pliku
graficznego i nie używamy adresu `og:image` jako miniatury, dopóki nie ma
udokumentowanej podstawy dla konkretnego obrazu. Link do oryginalnego materiału
zawsze pozostaje widoczny.

## Kiedy można włączyć miniaturę

Miniatura może zostać włączona dla konkretnego obrazu tylko, gdy w karcie
źródła lub przy samym materiale zapisano wszystkie poniższe informacje:

1. licencję pozwalającą na publiczne użycie także komercyjne i na techniczne
   przetworzenie potrzebne do miniatury (np. CC BY, CC0 lub jednoznaczna zgoda
   wydawcy),
2. adres oryginału, adres licencji, autora lub właściciela praw, jeżeli jest
   podany, oraz datę sprawdzenia,
3. informację, że miniatura jest przetworzonym obrazem, oraz wymagane
   oznaczenie autora i źródła,
4. brak sygnału, że fotografia pochodzi od agencji, fotografa zewnętrznego lub
   innego dostawcy, którego warunki są inne niż warunki wydawcy.

Brak któregokolwiek elementu oznacza ikonę zastępczą. Nie zakładamy licencji
na podstawie samego faktu, że obraz jest publicznie widoczny.

## Źródła już sprawdzone

### gov.pl

Stopka gov.pl rozdziela licencję tekstu (CC BY-SA 4.0) od materiałów
audiowizualnych, w tym zdjęć (CC BY-NC-ND 4.0), o ile strona nie mówi inaczej.
Licencja ND nie daje bezpiecznej podstawy do zmniejszania lub kadrowania zdjęć;
NC nie pasuje też do portalu, który może mieć wsparcie lub reklamę. Dla
materiałów gov.pl w MVP używamy więc własnych ikon. Wyjątkiem może być obraz z
indywidualnie wskazaną, szerszą licencją, zapisany w karcie materiału.

### Senat RP

Senat dopuszcza ponowne wykorzystanie własnej informacji pod warunkiem podania
źródła, daty i informacji o przetworzeniu, a przy wskazanym autorze także jego
oznaczenia. Jednocześnie wprost wyłącza zdjęcia oznaczone jako PAP. Pobieracz
Senatu w MVP nie zapisuje obrazów. Miniatury można rozważyć później wyłącznie
po rozpoznaniu autora i oznaczeń na poziomie pojedynczej fotografii.

## Model wdrożenia po MVP

Przed pierwszym automatycznym pobraniem obrazu dodamy osobny rejestr praw do
miniatury. Będzie zawierał stan `dozwolona`, `zabroniona` albo `do sprawdzenia`,
oryginał, licencję, autora, wymagane oznaczenie i datę weryfikacji. Zadanie
pobierające przyjmie wyłącznie stan `dozwolona`; wszystkie pozostałe dostaną
ikonę kategorii. Dzięki temu późniejszy frontend może bezpiecznie pokazywać
miniaturę razem z linkiem do źródła i atrybucją.

## Źródła warunków

- gov.pl: https://www.gov.pl/web/mswia/aktualnosci
- Senat RP: https://www.senat.gov.pl/ponowne-wykorzystywanie-informacji-sektora-publicznego/
