# Fixtures RCL (legislacja.rcl.gov.pl) - tylko do testów offline

Żaden z tych plików nie został pobrany przez nas z RCL: do dnia 21.10.2026 nasz serwer nie miał zgody ani zgłoszonego adresu IP.

| plik | pochodzenie |
|---|---|
| lista_typ2.html, projekt_12414050.html, katalog_13223895_konsultacje.html, katalog_13179001_komisja.html | kopie publicznych stron RCL zapisane przez osoby trzecie we wrześniu i październiku 2026 (repozytorium sobolevbel/lexinform, licencja MIT, tests/fixtures/rcl); usunięte skrypty i komentarze, imiona i nazwiska pracowników po "wprowadzony przez" zastąpione tekstem zastępczym |
| katalog_13223895_konsultacje_z_uwagami.html | ta sama strona z dopisanymi dokumentami w pustych folderach "Stanowiska..." i "Odniesienie...", z wymyślonymi podmiotami (Stowarzyszenie Przykładowe, Izba Wzorcowa) |
| katalog_lobbing_syntetyczny.html | wymyślony katalog etapu "Zgłoszenia lobbingowe" wg tego samego markupu |
| odrzucone_przez_zapore.html | typowa odpowiedź zapory (HTTP 200, tytuł "Request Rejected") |
| robots_*.txt | robots.txt: wariant "Disallow: /" (taki plik serwis zwracał we wrześniu 2025 wg Common Crawl) i wariant z dopuszczeniem naszego agenta |

Do potwierdzenia na pierwszej nocy: czy strona katalogu etapu "Zgłoszenia lobbingowe" i foldery "Stanowiska zgłoszone..." mają dokładnie taki markup jak w kopiach (tryb rozpoznania zapisze surowe strony do porównania).
