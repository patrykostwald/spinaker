# Jak zrobić pierwsze prawdziwe wydanie Tygodnika (dla właściciela, ok. 5 minut)

Skrypt `tygodnik.py` tylko CZYTA bazę: nic nie zapisuje, nic nie wysyła, nie łączy się z RCL. Sprawdzony na bazie testowej.

## Krok 1: zaloguj się na serwer
Otwórz terminal (Windows: PowerShell) i wklej:
```
ssh ubuntu@148.113.242.109
```

## Krok 2: pobierz skrypt z gałęzi Kartografa (bez zmiany tego, co działa na serwerze)
Wklej całość:
```
cd /srv/spin-clinic
git fetch origin cloud/zarobek-kartograf
git show origin/cloud/zarobek-kartograf:eksperyment-zarobek/kartograf/materialy/tygodnik.py > /tmp/tygodnik.py
```

## Krok 3: uruchom skrypt
Wklej całość (to jedna komenda):
```
docker compose --env-file .env.production -f deploy/docker-compose.production.yml exec -T backend python manage.py shell < /tmp/tygodnik.py > /tmp/tygodnik_wynik.md
```

## Krok 4: pokaż wynik
```
cat /tmp/tygodnik_wynik.md
```
Skopiuj wszystko, co się wyświetli, i wklej w rozmowie z Kartografem (albo koordynatorowi).
Jeśli wynik jest bardzo długi, wklej przynajmniej tabelę na górze i jedną branżę.

## Co dostaniesz
- tabelę: ile projektów było „w ruchu” w ostatnich 7 dniach w każdej z 9 branż, ile nowych stanowisk z konsultacji
  i zgłoszeń lobbingowych - to liczby do strony T1 i oferty T2;
- listę projektów dla każdej branży z etapem i linkiem do RCL.
Nazwy autorów zgłoszeń są pokazane tylko, gdy wyglądają na organizację; inne są ukryte (RODO).

## Gdy coś pójdzie nie tak
- `No such file` w kroku 3: krok 2 się nie udał - sprawdź, czy jesteś w `/srv/spin-clinic`.
- Błąd z `ImportError` lub `FieldError`: wklej go Kartografowi, poprawi skrypt.
- Pusta tabela (same zera): pobieranie z RCL jeszcze nie zapisało zmian z ostatnich 7 dni.
