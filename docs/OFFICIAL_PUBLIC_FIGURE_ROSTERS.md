# Oficjalne rostery osób publicznych

Ten importer służy dla stanowisk, dla których nie ma jednego krajowego API:
marszałków województw, prezydentów miast, burmistrzów oraz władz partii.

Każdy wiersz wymaga dwóch bezpośrednich adresów HTTPS: profilu danej funkcji
oraz oficjalnego wykazu, który ją potwierdza. `source_key` jest stałym,
instytucjonalnym identyfikatorem wpisu; nie wolno używać w nim imienia,
nazwiska, PESEL ani identyfikatora konta społecznościowego.

Szablon: `docs/templates/official-public-figure-roster.csv`.

Najpierw sprawdź plik bez zapisu:

```powershell
docker compose exec backend python manage.py import_official_public_figure_roster /app/docs/templates/official-public-figure-roster.csv --scope regional-marshals
```

Po sprawdzeniu danych zapisz je z `--apply`. Wpisy, których nie ma w kolejnym
kompletnym rosterze tego samego zakresu, są tylko oznaczane jako historyczne;
nigdy nie są usuwane.

Importer nie łączy osób po nazwisku, nie tworzy kont X, nie pobiera danych KRS
i odrzuca pliki z PESEL, datą urodzenia lub adresem.
