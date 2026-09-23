# Odkrywanie oficjalnie podlinkowanych kont X

Ten etap pomaga redakcji odnaleźć tylko linki X/Twitter, które zostały jawnie opublikowane na oficjalnych profilach wpisów Sejmu, Senatu lub Parlamentu Europejskiego.

Nie korzysta z `api.x.com`, nie wyszukuje nazwisk w X, nie zgaduje handle'i na podstawie imienia, nie tworzy automatycznie kandydatur i nie uruchamia pobierania postów.

## Podgląd małej partii

```powershell
docker compose exec backend python manage.py discover_official_social_handles --source sejm --limit 10 --dry-run
```

Po sprawdzeniu wyniku uruchom ten sam wariant bez `--dry-run`. Zaczynaj od 10–25 profili. Dopuszczalny limit jednego uruchomienia to 100.

Dowody pojawią się w Django Admin w pozycji **Dowody kont społecznościowych**. Redaktor otwiera link do oficjalnego profilu oraz znaleziony link X, a następnie wybiera akcję **„Po przeglądzie utwórz kandydatury kont”**.

Ta akcja tworzy wyłącznie `PoliticalAccountCandidate` z klasyfikacją „Niezależne / do oceny” i pustą grupą pobierania. Przed jakimkolwiek sprawdzeniem w X redaktor musi ręcznie przypisać właściwą klasyfikację i sprawdzić, czy konto nadal jest aktualne.
