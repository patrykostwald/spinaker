# Fixtures 090

Próbki **syntetyczne / skrócone przykłady kontraktów**, nie pobrane odpowiedzi
produkcyjne. Odczyty Python/HTTPS w środowisku wykonawczym 3.10.2026 zakończyły
się WinError 10013. Żadnych zapytań Meta API nie wykonano.

`api.json` i `speech.html`: kształt pól według https://api.sejm.gov.pl/sejm.html
(głosowania, interpellations, writtenQuestions, proceedings, transcripts, MP, prints).
Nazwy osób i treści zastąpione fikcyjnymi. Meta: kontrakt ads_archive, przykład
syntetyczny obejmuje również celowo niebezpieczny paging.next i snapshot z tokenem.

HTML: minimalne kontrakty parserów, NIE zapis rzeczywistego DOM:
- https://www.gov.pl/web/mswia/dzialalnosc-lobbingowa
- https://www.sejm.gov.pl/sejm10.nsf/page.xsp/lobbing
- https://www.sejm.gov.pl/sejm10.nsf/lobbing_osoby_tab.xsp
- https://www.sejm.gov.pl/sejm10.nsf/posel.xsp?id=400&type=A
- https://pkw.gov.pl/finansowanie-polityki/finansowanie-partii-politycznych

`osr.txt`: syntetyczny układ tabeli dla parsera przeniesionego z pilotażu
`lobbing-pilotaz/skrypty/konsultacje.py` (scan, parse_table, parse_reverse_table).
`register.txt`: syntetyczna warstwa tekstowa rejestru; parser heurystyczny.
Nie są to fixtures potwierdzające zgodność z żywym HTML/PDF; przed uruchomieniem
potrzebny jest kontrolny odczyt w granicach zatwierdzonej karty dostępu.
