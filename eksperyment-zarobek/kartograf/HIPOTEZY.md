# Hipotezy - Kartograf (runda 1)

Mapa rynku i źródła: `materialy/mapa-rynku.md`. Ceny konkurencji [DP] - z fragmentów wyszukiwarki, do sprawdzenia na stronach.

### H1: Branżowy tygodnik legislacyjny dla izb gospodarczych
- **Kto płaci:** izby i związki branżowe, które obiecują członkom monitoring prawa (PIH, e-Izba, Izba „Wodociągi Polskie” - linki
  w mapie rynku). KIG zrzesza ok. 160 organizacji (https://www.infor.pl/eksperci/366,6,Krajowa-Izba-Gospodarcza.html);
  wszystkich izb w Polsce [szacunek: 300-600, brak źródła].
- **Problem:** monitoring robi u nich etat albo nikt (Pracodawcy RP szukają 2 specjalistów ds. legislacji -
  https://www.pracuj.pl/praca/specjalista-specjalistka-do-spraw-legislacji-warszawa-bernenska-8,oferta,1004963458).
  Dlaczego teraz: 589 aktów w I półroczu 2026 (https://grantthornton.pl/publikacja/barometr-prawa-2026/), izby planują budżety na 2027.
- **Oferta i cena:** cotygodniowy przegląd jednej branży z etapu rządowego (projekt, konsultacje, lobbing, terminy uwag) prostym
  językiem + panel; izba może rozsyłać go członkom ze stopką „przygotowuje iapply, źródło RCL”. **990 zł netto/mies. za branżę**
  [szacunek], 3 mies. pilotażu po 490 zł. Porównanie: Vigilex 5 modułów 417 zł/mies. dla jednego czytelnika, bez redakcji;
  etat specjalisty [szacunek: 10 tys. zł/mies.]. Ta sama cena dla wszystkich (karta, zasada 5).
- **Kanał popytu:** strona z przykładowym wydaniem + formularz „chcę pilotaż” (ruch przychodzący), posty iapply, polecenia
  właściciela, partnerzy od Łącznika. Bez zimnych maili do izb. Koszt dotarcia: 0-300 zł reklamy [szacunek].
- **Dowód popytu:** izby wpisują monitoring do korzyści członkowskich i planów (linki wyżej); żadna nie publikuje ceny. Słaby punkt:
  brak dowodu, że kupią z zewnątrz - to sprawdza test T2.
- **Pierwsza faktura:** najwcześniej ok. 30 dni po zgodzie [szacunek]: 2 tyg. na stronę i pierwsze wydanie, rozmowa z 1 izbą
  z polecenia, pilotaż 490 zł. Warunek: ruszy pobieranie z RCL (wyjaśnienie robots.txt - PYTANIA P1).
- **Przychód 90 dni:** pesymistycznie 0 zł; realistycznie 2 izby x 2 mies. x 490 zł = 1960 zł netto [szacunek].
  Koszt danych i modeli prawie zero (PCSS 0,61 zł / 1 mln tokenów - ZASOBY.md).
- **Czas:** właściciel 3-5 h (zgody, 1-2 rozmowy) [szacunek]; zespół: Codex/Claude 2-3 dni na szablon i wysyłkę.
- **Zasoby iapply:** zgoda RCL, `backend/scraper/rcl_*`, API `news.rcl_api`, PCSS, Konsylium (kontrola streszczeń), poczta.
- **Ryzyko 2/5:** źle streszczony projekt = szkoda wizerunkowa. Zmniejszenie: drugi model sprawdza zgodność z dokumentem,
  „nie wiem” zamiast zgadywania, link do źródła przy każdym zdaniu, dopisek „to nie porada prawna”, warunki zgody RCL.
- **Test 48 h:** T2 w `TESTY.md`.
- **Ocena 7/10:** powtarzalne, tanie w produkcji, używa naszej przewagi (zgoda RCL); słabe - nieznana chęć zakupu z zewnątrz,
  wolny cykl decyzji izb.

### H2: Tani tygodnik branżowy dla firm i kancelarii (samoobsługa)
- **Kto płaci:** MŚP w branżach regulowanych (żywność, energetyka, transport, finanse), kancelarie i doradcy podatkowi
  (22 912 adwokatów i 42 721 radców - https://api.sejm.gov.pl/sejm/term10/interpellations/attachment/ATTDMXK2C/i12392-o1.pdf).
- **Problem:** darmowy alert RCL to dziesiątki maili bez interpretacji; płatne alerty zaczynają się od 84 zł (Vigilex) albo
  łapią projekt dopiero w Sejmie (SejmPage 139 zł) - https://www.lex.pl/zamowienie/vigilex,160037.html , https://sejmpage.pl/
- **Oferta i cena:** jeden mail w poniedziałek: zmiany w wybranej branży z etapu rządowego, terminy uwag, kto się zgłosił
  w lobbingu. **49 zł netto/mies. lub 490 zł/rok** [szacunek], płatność kartą, faktura automatycznie.
- **Kanał:** strona + lista oczekujących, posty, mała reklama, SEO na „projekt ustawy + branża”. Koszt dotarcia [szacunek: 30-80 zł
  za płacącego klienta przy reklamie].
- **Dowód popytu:** płatni konkurenci istnieją i mają cenniki (Vigilex, SejmPage) - rynek płaci; nasz dowód da T1.
- **Pierwsza faktura:** ok. 3-4 tyg. po zgodzie [szacunek]: strona, płatności, pierwsze wydanie.
- **Przychód 90 dni:** pesymistycznie 0-200 zł; realistycznie 25 klientów x 49 zł x 1,5 mies. = ok. 1840 zł [szacunek].
- **Czas:** właściciel 2-3 h; zespół 3-5 dni (płatności, konto klienta, wybór branży).
- **Zasoby:** jak H1 + zbudujmi.com (strona), automatyczne grafiki i filmy do postów.
- **Ryzyko 2/5:** jak H1 + regulamin usługi elektronicznej i RODO dla listy subskrybentów (dane osób, które same się zapisują - Prawnik).
- **Test 48 h:** T1 w `TESTY.md`.
- **Ocena 6/10:** szybka do zbudowania, ale mały przychód w 90 dniach i konkurencja z dużym wydawcą.

### H3: Raport konsultacji jednego projektu na zamówienie
- **Kto płaci:** agencje public affairs, organizacje branżowe, kancelarie, redakcje - gdy ważny projekt jest w konsultacjach
  (574 podmioty w rejestrze lobbingu - https://sejm.gov.pl/lobbing/informacja_roczna_2024.pdf).
- **Problem:** w RCL leżą dziesiątki stanowisk z konsultacji w plikach DOCX/PDF; ktoś musi je przeczytać i zestawić „kto chce czego”.
- **Oferta i cena:** raport w 48 h: lista uwag według przepisu, kto je zgłosił (tylko instytucje), co wnioskodawca przyjął
  (tabela odniesienia), punkty sporne. **790 zł netto za projekt** [szacunek]; brak publicznych cen konkurencji (agencje bez cennika).
- **Kanał:** strona z przykładem + formularz, Useme (odpowiedzi na publiczne zlecenia), polecenia.
- **Dowód popytu:** słaby - nie znaleźliśmy ogłoszeń na taki raport; jest pośredni (administracja kupuje monitoring mediów do 170 tys. zł:
  https://www.gov.pl/attachment/fb9a7248-8016-4df3-962a-267f23af9977).
- **Pierwsza faktura:** 2-3 tyg. [szacunek], bo jednorazowa sprzedaż bez abonamentu.
- **Przychód 90 dni:** pesymistycznie 0; realistycznie 3 raporty = 2370 zł [szacunek].
- **Czas:** właściciel 1 h na raport (przegląd), zespół pół dnia na szablon.
- **Zasoby:** `consultation_parser.py` (już w repozytorium), Konsylium, PCSS.
- **Ryzyko 3/5:** nazwy organizacji w raporcie (dane podmiotów, nie osób - przy osobach fizycznych usuwamy), ryzyko wizerunkowe
  przy sporach politycznych (jedna oferta dla wszystkich, bez ocen).
- **Test 48 h:** sekcja „Raport konsultacji” jako trzecia opcja na stronie T1 (bez dodatkowego kosztu).
- **Ocena 5/10:** może dać fakturę najszybciej, ale nie jest abonamentem i nie ma twardego dowodu popytu.

## Ślepe uliczki (też wynik)
- Monitoring legislacji jako osobny przetarg publiczny - nie znaleźliśmy ani jednego; siedzi w obsłudze prawnej (wymaga radcy).
- Monitoring mediów dla ministerstw (do 170 tys. zł) - duży popyt, ale wymaga licencji na prasę, radio i TV; poza naszym zasięgiem w 90 dniach.
- Alerty przetargowe - rynek pełny (PrzetargPro od 0 zł, Oferent, Och! Przetargi); Łowca zleceń zostaje narzędziem wewnętrznym (brief).
