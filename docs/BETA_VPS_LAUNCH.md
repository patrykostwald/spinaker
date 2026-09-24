# Uruchomienie beta.spin.clinic

Ten plan publikuje aktualnie zatwierdzony commit wyłącznie ręczną akcją GitHub. Nie ma automatycznego wdrażania po każdym commicie.

## 1. DNS

W strefie DNS domeny utwórz rekord:

| Typ | Nazwa | Wartość |
| --- | --- | --- |
| A | `beta` | publiczny adres IPv4 VPS |

Nie zmieniaj jeszcze rekordu głównej domeny `spin.clinic`.

## 2. Pierwsze przygotowanie VPS

Zaloguj się na VPS przez SSH i wykonaj jako administrator:

```bash
apt update && apt upgrade -y
apt install -y git docker.io docker-compose-plugin
systemctl enable --now docker
mkdir -p /srv/spin-clinic
```

Sklonuj prywatne repozytorium do `/srv/spin-clinic`. VPS potrzebuje własnego klucza SSH z dostępem tylko do odczytu repozytorium GitHub, aby później wykonać `git fetch`.

W repozytorium na VPS utwórz prywatny plik `/srv/spin-clinic/.env.production` na podstawie `deploy/.env.production.example`. Ustaw długie, losowe wartości `DJANGO_SECRET_KEY` oraz `POSTGRES_PASSWORD`. Nie zapisuj tego pliku w Git.

## 3. Dostęp GitHub Actions do VPS

Utwórz osobny klucz wdrożeniowy dla GitHub Actions i dodaj jego publiczną część do `~/.ssh/authorized_keys` użytkownika wdrożeniowego na VPS. W repozytorium GitHub utwórz środowisko `beta`, a w nim sekrety:

| Sekret | Wartość |
| --- | --- |
| `VPS_HOST` | publiczny adres IPv4 VPS |
| `VPS_USER` | użytkownik wdrożeniowy |
| `VPS_SSH_KEY` | prywatna część klucza wdrożeniowego |
| `VPS_PORT` | `22`, jeśli nie używasz innego portu |

## 4. Wdrożenie

Po propagacji DNS uruchom w GitHub ręcznie akcję **Deploy beta** na zatwierdzonym commicie. Caddy automatycznie wystawi certyfikat HTTPS dla `beta.spin.clinic`.

Przed uruchomieniem sprawdź lokalnie testy i build. Po wdrożeniu otwórz `https://beta.spin.clinic`, a następnie sprawdź stronę główną, źródła, osoby publiczne, materiały i logowanie.
