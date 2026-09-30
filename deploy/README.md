# Wdrożenie na VPS

Ten katalog jest gotowym szkieletem wdrożenia. Nie uruchamiaj go lokalnie ani nie zapisuj haseł w Git.

1. Na VPS skopiuj repozytorium do `/srv/spin-clinic`.
2. Skopiuj `.env.production.example` jako `/srv/spin-clinic/.env.production` i wpisz własne, długie sekrety.
3. Ustaw rekordy A dla `spin.clinic` i `www.spin.clinic` na IP VPS. Rekordy poczty pozostają bez zmian.
4. Z katalogu `deploy` uruchom: `docker compose --env-file ../.env.production -f docker-compose.production.yml up -d --build`.
5. Caddy sam pobierze certyfikat HTTPS po propagacji DNS.

PostgreSQL i Redis nie mają publicznych portów. Publicznie wystawione są tylko porty 80 i 443 przez Caddy.

## Naprawiacz i strażnik serwera (051)

Reguły, uzasadnienia i ograniczenia: [podręcznik naprawiacza](repairer-051.md).

Po wdrożeniu migracji 0095 worker i beat uruchamiają naprawiacza co 15 minut.
`REPAIRER_ENABLED=false` wyłącza go, `REPAIRER_DRY_RUN=true` włącza symulację.
Ręczny podgląd: `python manage.py repairer --dry-run` (JSON, bez napraw i maili).
Zbiorczy mail wychodzi przy pierwszym przebiegu od 8:00 Europe/Warsaw, najwyżej raz
dziennie i tylko z nowymi problemami. Adres jak u Rekrutera: `COUNCIL_RECRUITER_EMAIL`,
zapasowo `X_POST_ALERT_EMAIL` / `SOCIAL_VIDEO_EMAIL`; używa istniejącego SMTP.

Na VPS, po umieszczeniu repozytorium w `/srv/spin-clinic`, instalacja strażnika:

```bash
sudo cp /srv/spin-clinic/deploy/spin-watchdog.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now spin-watchdog.timer
```

Strażnik działa poza Dockerem jako root, co 5 minut. Stan przechowuje w
`/var/lib/spin-watchdog`, logi: `journalctl -t spin-watchdog`.
Sprawdza publiczne `https://spin.clinic/` i `/api/health/` (baza i cache).
Dla innej domeny ustaw `Environment=SPIN_WATCHDOG_URL=https://twoja.domena`
w override jednostki. Przy przeniesionym katalogu danych Dockera sprawdź, czy
leży na tej samej partycji co `/srv/spin-clinic` — skrypt mierzy tę partycję.
Nie usuwa wolumenów ani danych. Cooldown restartów: 30 minut, także po błędzie Dockera.
