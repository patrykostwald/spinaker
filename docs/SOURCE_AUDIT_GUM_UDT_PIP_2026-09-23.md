# Audyt kolejnej fali instytucji publicznych

Stan: 23 września 2026. Audyt dotyczy wyłącznie sposobu legalnego zasilania
Bazy metadanymi i linkiem do oryginału. Nie uruchomiono pobierania.

| Instytucja | Ustalenie | Decyzja |
|---|---|---|
| Główny Urząd Miar | GUM publikuje warunki ponownego wykorzystania, wymagające podania źródła oraz daty wytworzenia i pozyskania. Oficjalny serwis XML udostępnia kanał „Aktualności”, lecz przed jego użyciem prosi o przesłanie administratorowi nazwy serwisu, kontaktu i wybranego kanału. | `contact_required`: nie tworzyć karty ani nie pobierać kanału XML przed wysłaniem i zapisaniem tego zgłoszenia. Samodzielnie opisana strona RSS nie stanowi tu podstawy do uruchomienia niezidentyfikowanego endpointu. |
| Urząd Dozoru Technicznego | BIP UDT zezwala co do zasady na ponowne wykorzystanie informacji, przy atrybucji, dacie oraz oznaczeniu przetworzenia. W tym przeglądzie nie potwierdzono konkretnego, oficjalnego RSS/API z publikacjami nadającymi się do boxów. | Kandydat do dalszego audytu technicznego; bez aktywacji i bez zgadywania adresu feedu. |
| Państwowa Inspekcja Pracy | Polityka serwisu `pip.gov.pl` zabrania reprodukcji, powielania i rozpowszechniania publikowanych treści bez zgody właściciela praw autorskich. | `excluded`: nie dodawać do harvesterów ani nie pobierać metadanych automatycznie bez odrębnej, zapisanej zgody. |

## Źródła

- GUM — [RSS](https://www.gum.gov.pl/pl/rss), [XML i warunek uprzedniego zgłoszenia](https://www.gum.gov.pl/pl/xml), [warunki ponownego wykorzystania](https://bip.gum.gov.pl/bip/klient-w-urzedzie/ponowne-wykorzystywanie/789%2CPonowne-wykorzystywanie-informacji-publicznych.pdf).
- UDT — [warunki ponownego wykorzystania](https://bip.udt.gov.pl/home/ponowne-wykorzystywanie-informacji-sektora-publicznego).
- PIP — [polityka prywatności i praw autorskich](https://www.pip.gov.pl/polityka-prywatnosci).

## Następny ruch

GUM trafia do istniejącej kolejki kontaktowej z prośbą o dopuszczenie kanału
„Aktualności” wyłącznie do metadanych. Dla UDT trzeba najpierw znaleźć i
potwierdzić konkretny kanał. PIP pozostaje poza automatycznym pobieraniem.
