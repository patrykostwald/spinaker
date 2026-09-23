# MVP — stan przekazania na 23 września 2026

Ten dokument opisuje aktualną gałąź `codex/mvp-public-frontend`. Jest krótką
listą dla osoby, która jutro dopracowuje frontend, oraz dla redakcji uruchamiającej
źródła. Nie zastępuje kart dostępu ani zasad źródeł.

## Co jest gotowe w kodzie

- Baza materiałów: źródło, data, typ, kategoria i link do oryginału.
- Temat dnia: automatycznie dobrane materiały ułożone chronologicznie.
- Box i powiększony box: filtry, oś czasu, powiązania tekstowe oraz miejsce na
  reakcje i komentarze.
- Dr Spin: redakcyjna nitka kontekstowa. AI może przygotować propozycję, lecz
  człowiek wybiera materiały i publikuje.
- Konto: prywatne nitki, ulubione, zgłoszenia komentarzy i reakcje.
- Udostępnianie na X: pokazuje się wyłącznie po połączeniu konta użytkownika z
  X; użytkownik zawsze zatwierdza własny tekst i wysyłkę.
- Profile osób publicznych: ręcznie potwierdzone role, głosowania, relacje z
  podmiotami, oficjalne konto X i zapisane posty z tego konta. Nie ma PESEL,
  dat urodzenia, adresów ani automatycznego łączenia osób po nazwisku.
- Strony: `/o-nas`, `/osoby-publiczne`, `/konto`, demonstracje boxa i profilu.

## Wymagające lokalnego uruchomienia

W tym środowisku nie ma działającego Dockera, dlatego te kroki uruchamia osoba
pracująca przy lokalnym Compose:

```powershell
# Zatwierdza i uruchamia wyłącznie metadane RSS NIK, potem harmonogram odświeża je co godzinę.
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedNIKRss.ps1

# Ponawia bezpiecznie pilota ELI, dane.gov.pl i GUS po poprawce skryptu.
powershell -ExecutionPolicy Bypass -File .\scripts\Start-ApprovedOfficialMetadataPilots.ps1

# Sprawdza stan zatwierdzonych źródeł i pobrań.
docker compose exec backend python manage.py harvester_preflight
docker compose exec backend python manage.py sejm_pilot_status
```

## Zasada uruchamiania źródeł

Audyt RSS może sprawdzić technicznie, czy kanał działa, ale nie wolno mu
włączyć źródła. Aktywacja wymaga równocześnie ważnej, dokładnie pasującej karty
`SourceAccessInstruction`: operatora, endpointu, warunków użycia, dowodu,
limitu, daty i osoby zatwierdzającej. Kanał bez karty pozostaje kandydatem.

## Przed publicznym MVP

1. Ustawić domenę, HTTPS, kopie bazy, sekrety i monitoring błędów.
2. Uzupełnić kontakt, prywatność, zasady korzystania i źródeł.
3. Przetestować na lokalnym Compose zmienione moduły backendu i pełny build
   frontendu na komputerze, na którym działa Node bez blokady uprawnień.
4. Dopracować frontend bez zmieniania kontraktów API ani polityki prywatności.
5. Włączać kolejne oficjalne kanały pojedynczo, zawsze od metadanych i linku do
   oryginału.

## Sprawdzenie po tej serii zmian

```powershell
docker compose exec backend python -m pytest scraper/test_apply_audited_feeds.py scraper/test_configure_nik_rss_source.py news/test_public_figures_api.py -q
```

Pełny type-check frontendu należy uruchomić lokalnie. W tej sesji bezpośrednie
uruchomienie TypeScript zatrzymało się na uprawnieniach do lokalnego pakietu,
a nie na błędzie kodu.
