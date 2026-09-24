# Druga fala audytu archiwów

Stan: 14 września 2026. Kontrola obejmowała wyłącznie oficjalne robots.txt, sitemap, API i jawne indeksy archiwalne oraz małe próbki nowych i starych segmentów. Nie pobierano pełnych tekstów i nie obchodzono blokad.

## Dopuszczone do istniejącego importera sitemap

| Źródło | Lokalny ID | Mechanizm | Zakres próbki | Decyzja |
|---|---:|---|---|---|
| OKO.press | 24 | oficjalny indeks 37 map postów | 2022–2026 | `verified` |
| NaTemat | 27 | tygodniowe mapy postów | 2012–2026 | `verified` |
| PortalSamorzadowy.pl | 44 | indeks 21 paczek | stara i bieżąca paczka | `verified` |
| Infor.pl | 45 | indeks map artykułów | stara i bieżąca paczka | `verified` |

## Potwierdzony mechanizm, ale potrzebny osobny importer

- Money.pl: jawne archiwum dzienne od co najmniej 2001 roku.
- Newsweek Polska: kalendarz archiwum i archiwum wydań.
- Polityka: spisy treści wydań od 1999 roku; nie dowodzi to kompletności publikacji web-only.
- Krytyka Polityczna: oficjalne WordPress API, próbki 2009–2026.
- WysokieNapiecie.pl: oficjalne WordPress API, próbki 2011–2026.

Te źródła nie otrzymują automatycznie `can_backfill=true` w importerze sitemap. Najpierw wymagają ograniczonego adaptera dla archiwum HTML albo WordPress API.

## Wymagające zgody, dalszej kontroli albo zablokowane

- Onet ma kompletne archiwum techniczne, ale jego warunki jawnie zabraniają systematycznego pobierania bez zgody RASP. Nie uruchamiać bez licencji.
- Gazeta.pl ma archiwum historyczne, lecz robots zawiera prawne zastrzeżenie TDM i blokady wielu botów. Nie uruchamiać bez osobnej decyzji prawnej lub zgody.
- TVN24, Konkret24 i PAP: blokady robots dla badanej ścieżki.
- Demagog, Obserwator Finansowy i EurActiv.pl: aktualna blokada techniczna/WAF albo timeout; nie obchodzić.
- WP, DGP, Dziennik.pl, Fakt, Bankier.pl, Kultura Liberalna i Polskie Radio: brak potwierdzonego kompletnego mechanizmu historycznego.
- Do Rzeczy i Wprost: potwierdzone jedynie archiwa wydań, nie całych portali.
