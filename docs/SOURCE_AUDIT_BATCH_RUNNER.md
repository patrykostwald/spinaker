# Pełny przebieg kolejki audytu źródeł

Skrypt `scripts/Audit-AllPendingSourceCandidates.ps1` przechodzi przez wszystkie
kandydaty, które nie miały audytu w ostatnich siedmiu dniach. Działa partiami,
aby ograniczyć obciążenie zewnętrznych serwisów.

Nie aktywuje żadnego źródła, nie tworzy karty dostępu i nie pobiera materiałów.
Wyniki każdej paczki zapisuje w `reports/` jako JSON, CSV i Markdown. Dopiero
potwierdzony kanał wraz z zasadami ponownego użycia może dostać osobną kartę i
przejść do harvestera.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Audit-AllPendingSourceCandidates.ps1
```

Domyślnie skrypt wykonuje najwyżej dziesięć paczek po 24 źródła. Można zmienić
limit paczek bez zmiany charakteru audytu:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Audit-AllPendingSourceCandidates.ps1 -MaxBatches 20
```
