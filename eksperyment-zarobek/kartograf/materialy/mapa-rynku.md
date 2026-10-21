# Mapa rynku - monitoring prawa, zamówień i mediów w Polsce (runda 1, 21.10.2026)

Uwaga o źródłach: subagenci nie mogli otworzyć stron (WebFetch: błąd DNS, proxy 403), więc ceny pochodzą z fragmentów stron
pokazanych przez wyszukiwarkę. Wszystkie ceny są [DP], trzeba je sprawdzić na żywej stronie przed użyciem w ofercie (Prawnik:
twierdzenia porównawcze).

## 1. Kto sprzedaje i za ile

| Segment | Gracz | Co | Cena | Źródło |
|---|---|---|---|---|
| Prawo, za darmo | RCL legislacja.gov.pl | alert mailowy o zmianach projektu, bez interpretacji | 0 zł | https://legislacja.rcl.gov.pl/help/PomocnikUzytkownika.pdf |
| Prawo, za darmo | Monitor Legislacyjny, Sejm-Stats | śledzenie projektów | 0 zł | https://monitorlegislacyjny.pl/o-serwisie , https://docs.sejm-stats.pl/docs/intro |
| Prawo, tani abonament | Vigilex (LEX Hub, Wolters Kluwer) | poranne alerty o projektach, moduły branżowe | 84 zł netto/mies. (1 moduł), 250 zł (3), 417 zł (5) | https://www.lex.pl/zamowienie/vigilex,160037.html |
| Prawo, tani abonament | SejmPage | podsumowania AI „skutki dla biznesu”, od etapu Sejmu | 139 zł/mies. lub 1399 zł/rok; darmowy newsletter 1 obszar | https://sejmpage.pl/ |
| Prawo, drogo | Polityka Insight | analizy, newslettery | brak cennika; dawniej ok. 700-900 zł/mies. | https://www.wirtualnemedia.pl/rusza-polityka-insight-platny-serwis-z-analizami,7172543707739777a |
| Prawo, drogo | LEX, Legalis | systemy informacji prawnej z alertami | brak cennika; SN: 103 585,68 zł za Legalis na 2026 | https://www.sn.pl/pl/informacje/rejestr-umow-sadu-najwyzszego/2369 |
| Przetargi | Oferent | alerty przetargowe | 900 zł netto/kwartał, 2000 zł/rok | https://www.oferent.com.pl/cennik/ |
| Przetargi | PrzetargPro | BZP i TED, dopasowanie | 0 / 69 / 299 / 599 zł/mies. | https://przetargpro.pl/ |
| Przetargi | Och! Przetargi | ocena przetargów z AI | 150 i 300 zł/mies. | https://ochprzetargi.pl/ |
| Media | Newspoint | monitoring internetu | 169-999 zł netto/mies. | https://www.newspoint.pl/en/pricing |
| Media | IMM | prasa, radio, TV, internet | od 180 zł netto za hasło; raport od 900 zł | https://www.imm.com.pl/faq/ile-kosztuje-monitoring-mediow/ |

## 2. Kto płaci (dowody)
- **Administracja za monitoring mediów (świeże, duże):** Ministerstwo Sprawiedliwości 2026, do 170 000 zł za 8 mies.
  (https://www.gov.pl/attachment/fb9a7248-8016-4df3-962a-267f23af9977); Ministerstwo Kultury VI.2026, 12 mies.
  (https://www.gov.pl/web/kultura/zapytanie-ofertowe-dot-wykonywania-i-dostarczanie-codziennego-calodobowego-przegladu-mediow-prasy-radia-telewizji-oraz-internetu-mediow-spolecznosciowych-podcastow-2).
- **Monitoring legislacji jako osobny przetarg: nie znaleziono.** Siedzi w obsłudze prawnej gmin i spółek („informowanie o zmianach
  przepisów”), np. https://www.fripww.pl/zapytanie-ofertowe-na-obsluge-prawna-funduszu-rozwoju-i-promocji-wojewodztwa-wielkopolskiego-s-a/
- **Izby branżowe robią to dla członków w składce:** Polska Izba Handlu (https://pih.org.pl/korzysci-czlonkostwa/), e-Izba
  (https://eizba.pl/legislacja/), Izba „Wodociągi Polskie” - monitoring legislacyjny priorytetem na 2026
  (https://www.igwp.org.pl/zwyczajne-walne-zgromadzenie-czlonkow-igwp-absolutorium-dla-wladz-izby-nowe-plany-i-wybor-komisji-rewizyjnej/).
- **Związki pracodawców zatrudniają do tego ludzi:** Pracodawcy RP, 2 ogłoszenia (legislacja w ochronie zdrowia i nowe technologie)
  https://www.pracuj.pl/praca/specjalista-specjalistka-do-spraw-legislacji-warszawa-bernenska-8,oferta,1004963458 - koszt etatu
  to nasz sufit cenowy [szacunek: 8-12 tys. zł brutto/mies.].

## 3. Skala
- I półrocze 2026: 589 aktów (98 ustaw, 487 rozporządzeń) - https://grantthornton.pl/publikacja/barometr-prawa-2026/
- Lista projektów w RCL (widok z 8.09.2026): 2619 pozycji - kopia strony w `backend/scraper/fixtures/rcl/lista_typ2.html`.
- 574 podmioty w rejestrze lobbingu (stan przed 1.01.2025) - https://sejm.gov.pl/lobbing/informacja_roczna_2024.pdf
- 22 912 adwokatów i 42 721 radców (VI.2025) - https://api.sejm.gov.pl/sejm/term10/interpellations/attachment/ATTDMXK2C/i12392-o1.pdf
- KIG zrzesza ok. 160 organizacji - https://www.infor.pl/eksperci/366,6,Krajowa-Izba-Gospodarcza.html

## 4. Luka
Rynek ma dwie skrajności: darmowe alerty bez interpretacji (RCL) i drogie pakiety (LEX, Polityka Insight). Pośrodku tylko
alerty (Vigilex, SejmPage). **Nikt nie składa w jeden tygodniowy, branżowy przegląd prostym językiem trzech rzeczy z etapu
rządowego: projektu, uwag z konsultacji i zgłoszeń lobbingowych** - a my mamy na to zgodę RCL (także komercyjnie, ze źródłem).
SejmPage startuje dopiero od Sejmu, czyli 2-6 miesięcy za późno na uwagi [szacunek].
