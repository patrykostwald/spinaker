# Audyt: Urząd Patentowy i sądowe BIP-y

Stan: 23 września 2026. Audyt rozdziela dostępność kanału od dopuszczenia go
do automatycznego zasilania Bazy.

| Instytucja | Potwierdzone fakty | Decyzja |
|---|---|---|
| Urząd Patentowy RP | UPRP publikuje własną stronę RSS z kanałem aktualności. W tym przeglądzie nie znaleziono oficjalnej strony z warunkami ponownego wykorzystania obejmującymi ten kanał. | `contact_required`: zachować adres RSS jako kandydat, bez karty i importu do czasu otrzymania podstawy re-use. |
| WSA w Białymstoku | Oficjalny BIP publikuje katalog kanałów RSS oraz odsyła do zasad ponownego wykorzystania. Równocześnie informuje, że XML publikacji może zawierać pełną treść i załączniki. | Kandydat tylko dla przyszłego, wąskiego kanału `Aktualności`/komunikatów. Nie pobierać XML, załączników, całego BIP-u ani danych o sprawach przed osobnym filtrem prywatności i kartą dostępu. |
| Sąd Okręgowy w Warszawie | Oficjalny BIP ma RSS, zasady ponownego wykorzystania i komunikaty prasowe, ale wyświetla także informacje o konkretnych postępowaniach i osobach. | `manual_privacy_review`: nie automatyzować. Ewentualny przyszły pilot może objąć wyłącznie jednoznacznie ogólne komunikaty instytucjonalne, po zapisaniu filtra danych osobowych i podstawy użycia. |

## Zasady wynikające z audytu

1. Kanał RSS nie uprawnia do pobierania XML z pełną treścią lub załącznikami.
2. Sądy nie trafiają do wspólnego harvestera „aktualności” bez ograniczenia
   kategorii oraz przeglądu ryzyka ujawnienia danych procesowych.
3. Każdy przyszły importer zapisuje tylko tytuł, datę, opis z feedu, URL
   oryginału, źródło i czas pozyskania.

## Źródła

- [RSS UPRP](https://uprp.gov.pl/pl/rss)
- [Lista RSS WSA w Białymstoku](https://bip.bialystok.wsa.gov.pl/128/lista-kanalow-rss.html)
- [BIP Sądu Okręgowego w Warszawie](https://bip.warszawa.so.gov.pl/)
