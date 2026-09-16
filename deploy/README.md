# Wdrożenie na VPS

Ten katalog jest gotowym szkieletem wdrożenia. Nie uruchamiaj go lokalnie ani nie zapisuj haseł w Git.

1. Na VPS skopiuj repozytorium do `/srv/spin-clinic`.
2. Skopiuj `.env.production.example` jako `/srv/spin-clinic/.env.production` i wpisz własne, długie sekrety.
3. Ustaw rekordy A dla `spin.clinic` i `www.spin.clinic` na IP VPS. Rekordy poczty pozostają bez zmian.
4. Z katalogu `deploy` uruchom: `docker compose --env-file ../.env.production -f docker-compose.production.yml up -d --build`.
5. Caddy sam pobierze certyfikat HTTPS po propagacji DNS.

PostgreSQL i Redis nie mają publicznych portów. Publicznie wystawione są tylko porty 80 i 443 przez Caddy.
