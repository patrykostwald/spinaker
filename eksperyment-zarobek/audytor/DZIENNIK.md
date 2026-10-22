# Dziennik Audytora

## Runda 1 (21.10.2026)
- Zrobione: mapa 8 obowiązków (`MAPA.md`), 3 karty hipotez, 2 testy popytu, szkic oferty „Przegląd dostępności 2027”, opis skanera dla Warsztatu.
- Najważniejsze: 63 081 podmiotów publicznych, dostępność cyfrowa 36%; coroczny przegląd deklaracji do 31 marca; ministerstwo kupuje 100 audytów rocznie; ceny konkurencji 2 000-3 000 zł za stronę urzędową.
- Polski Akt o Dostępności (sklepy) działa od 28.06.2025, ale mikrofirmy usługowe są wyłączone [DP] - mniejszy rynek, niż się wydaje.
- AI Act: wysokie ryzyko przesunięte na 12.2027; art. 50 obowiązuje od 2.08.2026 - brak dowodu popytu w PL.
- Ślepe uliczki: KSC/NIS2 (duży rynek, brak kompetencji i referencji na 90 dni); raport o stanie dostępności dopiero 2029.
- Problem: WebFetch i curl bez DNS - pracowałem tylko na wynikach wyszukiwarki, stąd dużo [DP]. Subagentów nie uruchamiałem (oszczędność).
- Wartość rundy: jasny kierunek H1 z kanałem (zapytania publiczne + Łowca zleceń) i blokadą do zdjęcia (2 referencje).
- Dalsza praca (bez czekania na właściciela): zbudowałem skaner 0.1 (Playwright + axe-core po polsku, raport HTML/JSON, 1440 i 390 px), sprawdzony na stronie testowej. Warsztat ma mniej pracy.
- Potwierdzone z wyszukiwarki: art. 4 pkt 1 Polskiego Aktu o Dostępności wyłącza usługi mikroprzedsiębiorców ([RPO, 2.02.2026](https://bip.brpo.gov.pl/sites/default/files/2026-02/Do_MC_ozn_rozporzadzenie_projekt_komunikacja_elektroniczna_2_02_2026.pdf)); termin 31 marca widnieje w planach dostępności urzędów ([przykład gov.pl](https://www.gov.pl/attachment/35a4357f-aec6-46ff-905c-9868e0b50e8d)), ale nie znalazłem go w tekście ustawy - zostaje [DP].
- Firecrawl bez kredytów - odczyty stron nadal niemożliwe.

## Runda 2 (22.10.2026)
- Zrobione: `DZIALANIA/` - P1 szablon oferty na zapytanie publiczne z procedurą dla Kaia i cennikiem brutto, P2 oferta na Useme (2 wersje), P3 strona zbudujmi.com/dostepnosc (HTML gotowy), P4 post na Facebooku, KOLEJNOSC.md.
- Porażka rundy: nie znalazłem żadnego **otwartego** zapytania o audyt dostępności z terminem sprawdzonym na stronie ogłoszenia. Wyszukiwarka zwraca tylko zamknięte (PFRON 2021, Baza Konkurencyjności 07.2025, ministerstwo do 22.01.2026); strony się nie otwierają (brak DNS), Firecrawl bez kredytów. Dlatego P1 to szablon, a nie 3-5 wysłanych ofert.
- Strona P3 sprawdzona własnym skanerem: 0 błędów axe w 1440 i 390 px, w trybie jasnym i ciemnym; pomiar odstępów i krawędzi zgodny z zasadami designu.
- `materialy/przyklad-raportu.html`: przykładowy raport skanera (strona testowa, domena `example`) jako załącznik do ofert.
- Ustalenia rundy uwzględnione: bez płatnej reklamy (w P4 i P3 nie ma promocji, T2 z rundy 1 bez 150 zł), podpis współzałożyciela, przy wymogu KRS podpisuje prezes.
- Lista podmiotów z monitoringu ministerstwa 2026 ([labdostepnosci.pl](https://labdostepnosci.pl/2026/09/02/monitoring-dostepnosci-cyfrowej-2026-lista-podmiotow/)) to kusząca lista „gorących” klientów, ale pisanie do nich byłoby zimnym kontaktem - nie używam.
