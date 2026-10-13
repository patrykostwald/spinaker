# spina3.pl: instrukcja domeny i hostingu dla właściciela (szkic, nic nie wdrożone)

Zasada: ta sama aplikacja i baza co spin.clinic (VPS, Caddy, docker-compose w `deploy/`). Frontend spina3 to osobna statyczna strona
(prototyp Projektanta) albo Next.js; API pod subdomeną. Nie zmieniaj DNS ani produkcji bez decyzji; kroki poniżej wykonuje właściciel.

## 1. DNS (home.pl, domena spina3.pl)
| Rekord | Nazwa | Wartość | Uwagi |
|---|---|---|---|
| A | `@` | adres VPS (148.113.242.109) | strona |
| A | `www` | adres VPS | przekierowanie na `spina3.pl` |
| A | `api` | adres VPS | API: `https://api.spina3.pl/api/...` |
| CAA | `@` | `0 issue "letsencrypt.org"` | Caddy wystawia certyfikaty |
| TXT | `_dmarc` | `v=DMARC1; p=reject; rua=mailto:kontakt@iapply.pl` | domena nie wysyła poczty; SPF `v=spf1 -all` |
Drugi adres `spinki.org` (home.pl: A `@` i `www` -> VPS) -> 301 na `spina3.pl` (decyzja właściciela 14.10.2026; wcześniejszy pomysł `spinki.online` nieaktualny).

## 2. Caddy (dopisek do `deploy/Caddyfile`, po przeglądzie)
```
spina3.pl {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self'; connect-src 'self' https://api.spina3.pl; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        -Server
        -X-Powered-By
    }
    root * /srv/spina3/dist
    file_server
    @box path_regexp /box/\d+/
    rewrite @box /index.html
}
www.spina3.pl {
    redir https://spina3.pl{uri} permanent
}
api.spina3.pl {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        -Server
    }
    # API spina3 żyje pod /api/spina3/ w tym samym backendzie; na subdomenie skracamy ścieżkę.
    handle_path /api/* {
        rewrite * /api/spina3{uri}
        reverse_proxy backend:8000
    }
}
```
Boxy z linków czytelników odpowiadają z `X-Robots-Tag: noindex` (pole `Box.noindex`; nagłówek dodaje frontend/Caddy na `/box/<id>/`).

## 3. Zmienne środowiskowe (`.env.production`, tylko nazwy)
`SPINA3_ENABLED`, `SPINA3_PINS_ENABLED`, `SPINA3_LEVELS_VISIBLE`, `SPINA3_VIEWS_ENABLED`, `SPINA3_URL_PINS_ENABLED`, `ALLOW_IMAGE_PINS` (false),
`SPINA3_CHAINS_ENABLED` (false), `SPINA3_PUBLIC_PROFILES` (false), `SPINA3_ELECTION_SILENCE_START`, `SPINA3_ELECTION_SILENCE_END`,
`SPINA3_ELECTION_SILENCE_PAUSE_USER_PINS` (false), `SPINA3_ELECTION_SILENCE_PAUSE_RATINGS` (false), `SPINA3_ELECTION_SILENCE_PAUSE_COMMENTS` (false),
`SPINA3_RATINGS_ENABLED` (true), `SPINA3_COMMENTS_ENABLED` (true), `SPINA3_ADOPT_AUTHORLESS_BOXES` (true), `SPINA3_URL_FETCH_ENABLED` (false do czasu osobnego procesu), `SPINA3_IMPORT_PRESS` (false),
`SPINA3_AUTH_MODE` (session | token), `SPINA3_MODE` (zgodnosc | popularnosc), `SPINA3_PUBLIC_URL`, `SPINA3_SPIN_CLINIC_URL`, `SPINA3_PRZESZLOSC_URL`,
`SPINA3_PRZESZLOSC_PERSON_PATH`, `SPINA3_DR_SPIN_USERNAME`, `SPINA3_SSO_ISSUER`, `SPINA3_SSO_AUDIENCE`, `SPINA3_SSO_CODE_MAX_AGE`, `SPINA3_SSO_TOKEN_MAX_AGE`.
Do istniejących: `CORS_ALLOWED_ORIGINS` dopisać `https://spina3.pl`; `DJANGO_ALLOWED_HOSTS` dopisać `api.spina3.pl`; `CSRF_TRUSTED_ORIGINS` przy trybie sesji.

## 4. Etapy włączania (PETLA 6.1)
- Etap 0 "czytnik": `SPINA3_PINS_ENABLED=false`, `SPINA3_RATINGS_ENABLED=false`, `SPINA3_COMMENTS_ENABLED=false`, `SPINA3_LEVELS_VISIBLE=false`; importer i migawka działają; RSS, Zasady, Regulamin po prawniku.
- Etap 1 "zamknięta beta": `PINS_ENABLED=true`, zasłona kalibracyjna 14 dni (`LEVELS_VISIBLE=false`), URL wyłączone.
- Etap 2: `URL_PINS_ENABLED=true` razem z `URL_FETCH_ENABLED=true` tylko w osobnym procesie bez dostępu do sieci wewnętrznej, `VIEWS_ENABLED=true`.

## 5. Wspólne logowanie (konto.iapply.pl)
Trzy domeny to trzy eTLD+1: ciasteczko sesji nie przechodzi. Usługa logowania to ten sam backend pod `konto.iapply.pl` (DNS A, Caddy jak wyżej,
`ALLOWED_HOSTS`). Przepływ i tokeny: `backend/spina3/sso.py`. Tryb `SPINA3_AUTH_MODE=token` włączać dopiero po przeglądzie bezpieczeństwa
(czas życia 15 min, rotacja pseudonimu = wylogowanie wszędzie). Do decyzji: osobny klucz podpisu `SPINA3_SSO_SECRET` przy rozdzieleniu usług.

## 6. Migracja bazy i kopie
- Migracje: `backend/spina3/migrations/0001_initial.py` i `0002_v2_ratings_comments.py` (v2: oceny, komentarze, jedno przypięcie na box;
  tylko tabele `spina3_*`; żadnych zmian w `news`). Aplikacja nie była wdrożona, więc 0002 nie przenosi danych. Na produkcji dopiero po decyzji:
  najpierw kopia (`deploy/backup.sh`), potem `docker compose ... exec backend python manage.py migrate spina3`.
- Kopie: ten sam `backup.sh` (pg_dump całej bazy obejmuje tabele spina3). Migawki rankingu są w bazie (12 ostatnich + jedna na dobę przez rok).
- Dziennik zdarzeń: retencja 12 miesięcy (`event_retention_days`), czyszczenie `spina3.events.purge()` (do dopięcia w `spina3_sync` po decyzji prawnika).

## 7. Cron (po wdrożeniu)
`*/10 spina3_snapshot`, `*/15 spina3_sync`, tygodniowo `spina3_metrics`. Kolejka URL z pobieraniem: osobny kontener/proces z `SPINA3_URL_FETCH_ENABLED=true`
i bez dostępu do sieci wewnętrznej (SSRF).

## 8. Komenda wdrożenia (gdy właściciel zdecyduje)
```
ssh ubuntu@148.113.242.109
cd /srv/spin-clinic && git fetch && git checkout --detach origin/codex/mvp-public-frontend \
 && docker compose --env-file .env.production -f deploy/docker-compose.production.yml up -d --build --force-recreate
```
Przed tym: PR i przegląd, zielone testy, kopia bazy, wpisy DNS, Caddyfile, zmienne środowiskowe przez nano.
