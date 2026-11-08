# przeszłość.today: pętla person, runda 2 (6.11.2026)

Trzy persony przeszły przez żywe API produkcji (wdrożenie `5dc04bd`), po jednej, z odstępem między zapytaniami (zasada z rundy 1: 2-3 persony naraz, bez równoległych wywołań, 429 nie liczy się jako usterka). Narzędzie to Firecrawl bez wykonywania JS, więc widoków przeglądarkowych (telefon) **nie oceniano**; oceny dotyczą danych, komunikatów i śladu źródła w odpowiedziach API.

## Oceny

| Persona | Cel | Runda 1 | Runda 2 |
|---|---|---|---|
| Obywatel (telefon) | „jak głosował mój poseł” (okręg Kraków) | 3 | **7** |
| Compliance / KYC | due diligence ORLEN S.A. i Fundacji Orlen | 3 | **5** |
| Radny / aktywista lokalny | gmina Niegowa / Pionki: zamówienia, fundusze | 3 | **3** |
| Średnia (3 persony) | | 3,0 | **5,0** |

Próg pętli: średnia co najmniej 7, żadna persona poniżej 6 (nie osiągnięty). Porównanie dotyczy tylko tych trzech ról; pełna runda 10 person powtórzy się po wdrożeniu poprawek.

## Co zadziałało
- „Mój poseł” (Kraków: 22 posłów), „Oddane głosy: 1535 z 1865 (82,3%)”, filtr zgodności z klubem, odstępstwa z opisem metody i zdaniem „Odstępstwo nie jest zarzutem”, ślad źródła i link do Sejmu przy każdym głosie.
- Tożsamość i źródła spółki (KRS/NIP/REGON, link do rejestru), kwoty wątpliwe oznaczone (`amount_suspect`) i **wyłączone z sum** (sprawdzone w `news/drzewo_pieniedzy.py::_sums`; obawa persony, że suma 4,02 mld zł je zawiera, była niesłuszna), 1,5% podatku osobno od dotacji, stan danych z licznikiem źródeł.

## Wnioski i status
| # | Wniosek | Persony | Status |
|---|---|---|---|
| 1 | **Jednostki samorządu i podmioty bez KRS nie są wyszukiwalne** (gmina nie ma KRS; komunikat „wpisz numer KRS” nie pomaga); BZP „po NIP” (3513 rekordów) nie ma widoku „zamówienia po NIP zamawiającego” | radny, KYC | **otwarte** (największa luka; plan niżej) |
| 2 | Pole `vat` było gołym `null` bez powodu | KYC | **poprawione w kodzie** (powód: „jeszcze nie pobrano” albo „brak NIP”) |
| 3 | Osoby przy podmiocie: wyglądało na pusty/niepełny KRS, a lista obejmuje tylko osoby publiczne | KYC | **poprawione w kodzie** (stała notatka o zakresie i RODO) |
| 4 | Dwie liczby w Odstępstwach (76 odstępstw vs 41 „głosów wbrew klubowi”) bez wyjaśnienia | obywatel | **poprawione w kodzie** (`legend` w odpowiedzi posła: „odstępstwa” = wszystkie inne niż większość klubu, „wbrew klubowi” = tylko przy zgodności klubu >= 80%) |
| 5 | Echo filtrów wpisywało zgodność z klubem w pole `klub`; tytuły ucięte w pół słowa; trzy różne identyfikatory (slug, id Sejmu) | obywatel | **poprawione w kodzie** (echo `zgodnosc`, tytuł do całego słowa z wielokropkiem po następnym przeliczeniu, `sejm_id` i skrót odstępstw przy pośle w „Mój poseł”) |
| 6 | Lista głosowań posła nieczytelna dla laika (setki „poprawka 2”); temat tylko przy części | obywatel | otwarte; temat z procesu legislacyjnego jest, brak domyślnego widoku „całość projektu ustawy” |
| 7 | /temat/ miesza treści niezwiązane z tematem (filmy YouTube) | radny | otwarte (do zbadania) |
| 8 | Pełne organy spółek (zarząd, RN, beneficjenci rzeczywiści), sankcje/PEP, sprawozdania finansowe | KYC | poza zakresem (dane osobowe zwykłych członków organów nie są zbierane; CRBR niedostępny) |
| 9 | Dotacje UE per gmina (Kohesio puste, FTS po VAT) | radny | otwarte (lista projektów UE 2021-2027 ma tylko nazwę beneficjenta, bez NIP) |

## Plan na wniosek 1 („podmiot po NIP”)
Widok i endpoint `GET /api/przeszlosc/podmiot/<NIP>/`: ogłoszenia BZP (zamawiający po `organizationNationalId`), TED (wykonawca/zamawiający po NIP), FTS (po VAT), status VAT (Biała lista) oraz nazwa z Białej listy, także gdy podmiot nie ma KRS (JST, jednostki budżetowe). Wyszukiwarka `/spolki/` przy NIP spoza bazy kieruje na ten widok; przy zapytaniu o „gmina/urząd/miasto” komunikat „JST nie ma KRS: szukaj po NIP zamawiającego”. Bez zapisywania osób; nazwa i adres siedziby tylko podmiotu.
