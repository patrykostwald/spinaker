# Poczta wychodząca - kolejka listów (właściciel 7.10)

Każdy plik `*.md` w tym katalogu to jeden list. Pliki zaczynające się od `_` są opisami, nie listami.
Wysyłka: `python manage.py poczta --wyslij-kolejke --plan` (tylko pokazuje), `python manage.py poczta --wyslij-kolejke` (wysyła).
W kontenerze katalog jest kopiowany przez `deploy/wdrozenie-0610.sh` (sekcja 14) do `/app/poczta-wychodzaca`.

## Nagłówek (między liniami `---`)
- `to` - adres e-mail adresata; pusty = list czeka na adres (plan pokazuje `contact_url`). Adresów nie zgadujemy:
  tylko ze strony kontaktowej adresata albo z rejestru w repo (`docs/emails`, `docs/SOURCE_CONSENT_RECIPIENTS_*`), źródło w `source`.
- `subject` - temat.
- `mailbox` - `SPIN` | `IAPPLY` | `PATRYK` (nazwa z `MAILBOXES`; wnioski spółki do urzędów z `IAPPLY`, listy zespołu spin.clinic ze `SPIN`).
- `category` - `dostep-do-danych` | `instytucja` | `partner` | `odpowiedz`.
- `lang` - `PL` (domyślnie) | `EN` (wyłącza sprawdzenie „po polsku”).
- `attachments` - nazwy plików z tego katalogu, po przecinku (opcjonalnie).
- `not_before` - data `RRRR-MM-DD`, przed którą list czeka.
- `hold` - powód wstrzymania; list z `hold` nigdy nie idzie (usuń linię, żeby odblokować).
- `reply_to_item` - klucz wcześniejszego listu: wysyłka w jego wątku (`In-Reply-To`), dopiero gdy tamten wyszedł.
- `contact_url`, `source` - strona kontaktowa adresata i skąd adres.

## Treść
Treść listu bez stopki: stopkę (dane spółki ze stron prawnych serwisów) dodaje szablon skrzynki, własną daje zmienna
`MAILBOX_<NAZWA>_SIGNATURE` (literalne `\n` to nowa linia; prawdziwy format pokaże `poczta --podpis <NAZWA>`).
Miejsce `{{PODPIS}}` (wnioski do urzędów) wypełnia `MAIL_OUTBOX_SIGNER="Imię Nazwisko, funkcja"` z `.env.production` - nigdy w repo.

## Kontrola przed wysyłką (stała, bez modelu)
Bez oferty handlowej przy pierwszym kontakcie (PKE art. 398), bez obietnic pieniędzy, bez adresów, telefonów i PESEL osób trzecich,
krótki myślnik, po polsku (chyba że `lang: EN`), ton rzeczowy, bez miejsc `[do uzupełnienia]`. Duplikaty: rejestr `MailOutboxLog`
i folder Wysłane skrzynki (ten sam adresat i podobny temat w 60 dni). Limit `MAIL_OUTBOX_DAILY_LIMIT` (10 na skrzynkę dziennie).
Każda wysyłka: kopia w folderze Wysłane, wpis w rejestrze i pozycja w zestawieniu 7:10 do właściciela.
