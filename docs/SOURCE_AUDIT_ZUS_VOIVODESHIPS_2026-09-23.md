# Audyt: ZUS i urzędy wojewódzkie

Stan: 23 września 2026. Zakres audytu to wyłącznie przyszłe boxy z metadanymi
i odnośnikiem do oryginału.

| Instytucja | Potwierdzone fakty | Decyzja |
|---|---|---|
| ZUS | BIP ZUS publikuje zasady ponownego wykorzystania dla informacji udostępnionych w BIP i centralnym repozytorium. Nie potwierdzono bieżącego, konkretnego feedu/API aktualności ani zakresu, który nie zawiera danych ubezpieczonych. | `manual_channel_review`: nie aktywować całego BIP-u. Szukać tylko oficjalnego kanału ogólnych komunikatów, po czym zapisać ścisły filtr danych osobowych i kartę metadanych. |
| Urzędy wojewódzkie | BIP-y wojewódzkie udostępniają RSS i strony zasad ponownego wykorzystania. Są jednak odrębnymi operatorami i publikują również decyzje, ogłoszenia oraz dane wymagające redakcyjnego doboru. | Nie uruchamiać zbiorczego harvestera. Każdy urząd wojewódzki może wejść jako osobna karta, wyłącznie z kategoriami ogólnych komunikatów po odrębnym audycie RSS i prywatności. |

## Źródła

- [ZUS — zasady ponownego wykorzystania](https://www.zus.pl/en/web/biuletyn-informacji-publicznej/obsluga-klienta/ogolne-zasady-zalatwiania-spraw/ponowne-wykorzystywanie-informacji-sektora-publicznego)
- [Kujawsko-Pomorski Urząd Wojewódzki — mapa BIP i RSS](https://bip.bydgoszcz.uw.gov.pl/10/mapa-biuletynu.html)
- [Kujawsko-Pomorski Urząd Wojewódzki — warunki ponownego wykorzystania](https://bip.bydgoszcz.uw.gov.pl/359/158/ponowne-wykorzystywanie-informacji-sektora-publicznego.html)
- [Wielkopolski Urząd Wojewódzki — warunki ponownego wykorzystania](https://poznan.uw.gov.pl/ponowne-wykorzystywanie)
