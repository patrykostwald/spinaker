# Import kandydatur relacji z podmiotami

Polecenie tworzy tylko wpisy `wymaga potwierdzenia redakcji`. Nie pobiera danych z KRS samodzielnie, nie wyszukuje osób po nazwisku i nie przyjmuje PESEL, daty urodzenia ani innych ukrytych identyfikatorów.

## Plik CSV

Wymagane kolumny:

```text
person_name,organisation_name,krs_number,kind,official_register_url,public_role,relation_status,evidence_url,evidence_note
```

- `person_name` — dokładna nazwa istniejącej, aktywnej osoby publicznej w rejestrze.
- `krs_number` — dokładnie 10 cyfr.
- `kind` — `foundation`, `association`, `company` albo `other`.
- `relation_status` — `current` albo `former`.
- `evidence_url` — bezpośredni publiczny dowód konkretnej relacji, nie wynik wyszukiwania i nie samo dopasowanie nazwiska.

Kolumny `pesel`, `date_of_birth`, `birth_date` i `data_urodzenia` są celowo odrzucane.

## Przebieg

1. Najpierw podgląd:

```powershell
docker compose exec backend python manage.py import_public_figure_organisation_candidates C:\sciezka\relacje.csv
```

2. Po sprawdzeniu komunikatu zapisz kandydatury:

```powershell
docker compose exec backend python manage.py import_public_figure_organisation_candidates C:\sciezka\relacje.csv --apply
```

3. W panelu administracyjnym otwórz „Public figure organisation relations”, sprawdź źródło i użyj działania „Potwierdź wybrane relacje w źródle publicznym”.

Tylko relacja potwierdzona przez redaktora może później trafić do publicznego profilu.
