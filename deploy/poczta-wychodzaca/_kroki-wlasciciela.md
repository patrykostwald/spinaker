# Kroki właściciela - to nie idzie e-mailem (stan 7.10.2026)

Źródła: `Desktop\projekty\spin-clinic-maile\` (00-KOLEJNOSC.txt, dostep-do-danych\00-PODSUMOWANIE.txt).

## Pisma do urzędów przez ePUAP / e-Doręczenia (treść w plikach 01 i 02 tego katalogu)
1. Kancelaria Sejmu - ePUAP `/KSRP/SkrytkaESP` albo e-Doręczenia `AE:PL-30275-59799-JADHJ-27`; adresy sprawdź na
   https://www.sejm.gov.pl/sejm10.nsf/page.xsp/informacja_publ. Wklej treść `01-sejm-wniosek-dane.md`, w miejsce `{{PODPIS}}` imię, nazwisko i funkcję.
2. Kancelaria Senatu - ePUAP `/Kancelaria_Senatu/SkrytkaESP` albo e-Doręczenia `AE:PL-20189-46019-DVEJA-29`;
   https://www.senat.gov.pl/udostepnianie-informacji-publicznej/. Treść `02-senat-wniosek-dane.md`.
   Po wysłaniu obu: usuń linię `hold` w `08-watchdog-konsultacja.md` (list mówi „właśnie wysłaliśmy wnioski”).

## Dostęp do danych o opiniach (formularze i panele, nie e-mail)
3. Wykop API v3 (0 zł, ok. 10 min): zaloguj się kontem serwisowym, https://dev.wykop.pl/dashboard/app -> „Utwórz aplikację”,
   opis z `dostep-do-danych\wykop-api.txt`, strona https://spin.clinic. Klucz i sekret tylko do `.env.production` na serwerze.
4. Reddit Data API (ścieżka komercyjna): formularz z „Developer Documentation” w https://redditinc.com/policies/data-api-terms;
   gotowy tekst (EN) w `dostep-do-danych\reddit-api.txt`. Przed wysłaniem otwórz stronę i potwierdź aktualne wymogi.
5. Meta Content Library i TikTok Research API: tylko z partnerem badawczym (uczelnia albo NGO non-profit); wniosek składa partner w
   https://www.facebook.com/research-tools-manager i https://developers.tiktok.com/. List do partnera czeka w `90-partner-badawczy-meta-tiktok.md`:
   wskaż adresata (pole `to`) i usuń `hold`. Nie przedstawiamy się jako instytucja naukowa.
6. X API: już mamy; żaden wniosek nie jest potrzebny (kredyty na liście przypomnień).

## Formularze kontaktowe zamiast adresu (albo wpisz adres w `to`, gdy znajdziesz go na stronie kontaktowej)
7. OpenSanctions (05, potem 12 w tym samym wątku od 13.10): https://www.opensanctions.org/contact/ (EN, treść w plikach).
8. Bez adresu w plikach listów: 07 mamprawowiedziec.pl, 09 CEDMO, 10 AFP Sprawdzam, 13 Rejestr.io, 15 CLARIN-PL, 16 UW i UAM,
   17 Panoptykon, 19 NASK, 20 Batory, 21 EDMO, 22 GNI - adres ze strony w `contact_url`; po wpisaniu `to` list idzie automatycznie.

## Decyzje właściciela (listy wstrzymane `hold`)
9. 14 Frontstory, 18 OKO.press, 23 redakcje lokalne - propozycje bezpłatnego pilotażu lub zestawień: pierwszy kontakt z ofertą,
   agent ich nie wysyła (PKE art. 398); jeśli chcesz, usuń `hold` albo wyślij sam.
10. 24 PAP, 25 Brand24, 26 sondaże (IBRiS, Opinia24) - „po przychodach” (Twoja kolejność 6.10).
