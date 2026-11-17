# Reverse proxy (Caddy) na VPS - spin.clinic

Ten plik opisuje wyłącznie warstwę reverse proxy dodaną do `docker-compose.yml`
i `Caddyfile` w katalogu głównym repozytorium. Nie zmienia kodu backendu,
migracji ani harvesterów.

## Zakres

- Domeny: `spin.clinic`, `www.spin.clinic`.
- Caddy nasłuchuje na portach 80 i 443, automatycznie wystawia i odnawia
  certyfikat HTTPS (Let's Encrypt).
- `/api/*` i `/admin/*` -> `backend:8000`.
- Pozostałe ścieżki -> tymczasowo też `backend:8000`, dopóki frontend nie
  zostanie dodany jako osobna usługa w `docker-compose.yml`.
- PostgreSQL i Redis nie mają publicznych portów (dostęp tylko wewnątrz
  sieci Docker Compose).
- Port `8000` backendu pozostaje tymczasowo otwarty publicznie do testów -
  do usunięcia z `docker-compose.yml`, gdy cały ruch produkcyjny zostanie
  potwierdzony przez Caddy.

## Wymagania wstępne na VPS

- Zainstalowany Docker + wtyczka Docker Compose.
- Rekordy DNS A (i AAAA, jeśli używane IPv6) dla `spin.clinic` oraz
  `www.spin.clinic` wskazujące na publiczny adres IP VPS, w pełni
  propagowane.
- Otwarte porty 80 i 443 na firewallu VPS.
- Plik `.env` z sekretami skopiowany na serwer (nie z repozytorium Git).

## Uruchomienie

```bash
cd /sciezka/do/repo
docker compose pull
docker compose up -d --build
```

## Sprawdzenie statusu

```bash
docker compose ps
docker compose logs -f caddy
```

## Sprawdzenie certyfikatu HTTPS

Po propagacji DNS i pierwszym starcie Caddy (może potrwać do ok. 1-2 minut):

```bash
# Z zewnątrz VPS - sprawdza łańcuch certyfikatu i wystawcę
curl -vI https://spin.clinic 2>&1 | grep -i "subject\|issuer\|SSL certificate"
curl -vI https://www.spin.clinic 2>&1 | grep -i "subject\|issuer\|SSL certificate"

# Alternatywnie, jeśli openssl jest dostępny lokalnie
echo | openssl s_client -connect spin.clinic:443 -servername spin.clinic 2>/dev/null | openssl x509 -noout -issuer -dates
```

Oczekiwany wynik: wystawca `Let's Encrypt` (lub `ZeroSSL`, w zależności od
CA skonfigurowanego w Caddy), ważny certyfikat, brak błędów TLS.

Logi wydawania certyfikatu można też podejrzeć bezpośrednio:

```bash
docker compose logs caddy | grep -i "certificate\|acme"
```

## Zatrzymanie

```bash
# Zatrzymuje kontenery, zachowuje wolumeny (dane DB, certyfikaty Caddy)
docker compose down

# Tylko usługa caddy (np. do wymuszenia restartu bez ruszania reszty stosu)
docker compose restart caddy
```

## Uwaga

Nie uruchamiaj powyższych komend produkcyjnie bez wcześniejszego
potwierdzenia - ten dokument opisuje wyłącznie gotową konfigurację do
przeglądu.
