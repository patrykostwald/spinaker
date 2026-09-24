# Prompt do niezależnego sprawdzenia źródeł

Pomóż zweryfikować publiczne źródła dla polskiego archiwum publikacji. Nie wymyślaj adresów RSS/API/sitemap ani dostępności archiwów. Otwórz stronę wydawcy i podaj dowód (oficjalny URL oraz miejsce wskazujące kanał). Dla każdego źródła z listy ustal: działający RSS/Atom lub API, oficjalny indeks sitemap, dostępność historycznych publikacji, sposób odczytu oryginalnej daty, ograniczenia i datę weryfikacji. Nie traktuj HTTP200 strony HTML jako działającego RSS. Nie zastępuj daty publikacji datą aktualizacji. Nie omijaj logowania, płatnego dostępu ani blokad. Gdy nie potwierdzisz kanału, napisz „niepotwierdzone” i opisz próbę. Dołącz także potwierdzone regionalne i gminne źródła, jeśli znajdziesz je u wydawców. Bez X: posty użytkownik dodaje wyłącznie po URL do nitki.

Oczekiwany wynik: tabela nazwa | obecny URL | potwierdzony kanał | dowód u wydawcy | archiwum | data publikacji | ograniczenia. Osobno JSON z tymi samymi polami, bez spekulacji.

Źródła wymagające sprawdzenia (błąd lokalnego importu nie przesądza, że kanał nie istnieje):

- Dziennik Gazeta Prawna: https://www.gazetaprawna.pl/rss/wiadomosci.xml — HTTP 404
- Dziennik.pl: https://wiadomosci.dziennik.pl/rss — HTTP 404
- EurActiv.pl: https://euractiv.pl/feed/ — HTTP 522
- Fakt24: https://www.fakt.pl/rss/fakty.xml — HTTP 404
- Gazeta.pl: https://rss.gazeta.pl/pub/rss/gazetapl_wiadomosci.xml — HTTP 404
- Infor.pl: https://www.infor.pl/rss/wiadomosci.xml — Nieprawidłowy lub niedostępny RSS
- KPRM: https://www.gov.pl/web/premier/rss — Nieprawidłowy lub niedostępny RSS
- Kancelaria Prezydenta: https://www.prezydent.pl/rss/ — HTTP 404
- Konkret24: https://konkret24.tvn24.pl/feed — HTTP 404
- Ministerstwo Edukacji i Nauki: https://www.gov.pl/web/edukacja-i-nauka/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Finansów: https://www.gov.pl/web/finanse/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Infrastruktury: https://www.gov.pl/web/infrastruktura/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Klimatu i Środowiska: https://www.gov.pl/web/klimat/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Obrony Narodowej: https://www.gov.pl/web/obrona-narodowa/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Rolnictwa: https://www.gov.pl/web/rolnictwo/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Spraw Zagranicznych: https://www.gov.pl/web/dyplomacja/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Sprawiedliwości: https://www.gov.pl/web/sprawiedliwosc/rss — Nieprawidłowy lub niedostępny RSS
- Ministerstwo Zdrowia: https://www.gov.pl/web/zdrowie/rss — Nieprawidłowy lub niedostępny RSS
- NBP: https://nbp.pl/rss.xml — Nieprawidłowy lub niedostępny RSS
- NaTemat: https://natemat.pl/rss — HTTP 404
- O2.pl: https://www.o2.pl/feed — HTTP 404
- Obserwator Finansowy: https://www.obserwatorfinansowy.pl/feed/ — Nieprawidłowy lub niedostępny RSS
- Onet Wiadomości: https://www.onet.pl/informacje/rss — HTTP 404
- Polityka: https://www.polityka.pl/rss.xml — HTTP 404
- PortalSamorzadowy.pl: https://portalsamorzadowy.pl/rss.xml — HTTP 404
- RPO: https://bip.brpo.gov.pl/rss — HTTP 404
- Radio ZET: https://www.radiozet.pl/rss/news.xml — HTTP 404
- Rzeczpospolita: https://www.rp.pl/rss/1019.xml — HTTP 404
- Senat RP: https://www.senat.gov.pl/rss/aktualnosci.xml — HTTP 404
- TVP Info: https://www.tvp.info/rss/wiadomosci — HTTP 404
- Teraz Środowisko: https://www.teraz-srodowisko.pl/rss.xml — HTTP 404
- Wprost: https://www.wprost.pl/rss.xml — HTTP 404
