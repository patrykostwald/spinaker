# Przegląd: Paperclip i Hermes Agent

Data: 2026-10-11. Tryb: tylko odczyt (płytkie klony, nic nie zainstalowane ani uruchomione, bez `npm audit`).
Wersje: Paperclip `bfe7c6357d1e0c945c8cb84259153cb3b6542d28` (A), Hermes `1fd18277267152893a8a24792b79213e7ca3f899` (B).
Ścieżki poniżej są względne do klonów (`A/` = paperclip, `B/` = hermes-agent). Numery linii z dnia przeglądu.

Ograniczenia: nie sprawdzałem żywych stron regulaminów dostawców ani liczby gwiazdek/issues (brak API). Sekcja o regulaminie opiera się na kodzie projektów i mojej wiedzy, więc zweryfikuj ją na aktualnych stronach Anthropic i OpenAI przed decyzją.

## Podsumowanie

| | Paperclip | Hermes Agent |
|---|---|---|
| Licencja | MIT (`A/LICENSE:1`, `cli/package.json:16`) | MIT (`B/LICENSE:1`, `pyproject.toml:17`) |
| Aktywność | commit z 2026-10-11, wydania co kilka dni (`A/releases/`) | commit z 2026-10-11 |
| Stos | Node 24, pnpm, TS, Postgres wbudowany/zewnętrzny | Python 3.11-3.14, s6-overlay w Dockerze |
| Telemetria domyślnie | włączona (wyłączalna) | nie znalazłem telemetrii produktu; polityka "bez telemetrii bez opt-in" w manifestach MCP |
| Abonament bez klucza API | tak, przez oficjalne CLI `claude`/`codex` w izolowanym loginie | tak, ale przez **pożyczenie tokenu OAuth Claude Code** i podszywanie się pod klienta |
| Zgodność z regulaminem | niskie ryzyko (uruchamia prawdziwe CLI) | **wysokie ryzyko** (patrz pkt 4) |

Rekomendacja: Paperclip w utwardzonym Dockerze (pkt 8) jest do przyjęcia. Hermes tylko z kluczem API albo innym dostawcą, z `auth.adopt_external_logins: false`, bez żadnego dostępu do `~/.claude`.

## 1. Licencja i aktywność

- Obie MIT. Paperclip: `A/LICENSE`, `cli/package.json:16`, `server/package.json:4`. Hermes: `B/LICENSE`, `pyproject.toml:17`.
- Paperclip `0.3.1` (`cli/package.json:3`), ostatni commit "fix(ui): stack confirmation prompt..." (#15895) z 2026-10-11; wydania w `A/releases/` (np. `v2026.916.1.md`).
- Hermes `version = "0.0.0"` w `pyproject.toml:7` (wersjonowanie poza pakietem), ostatni commit 2026-10-11. Bardzo duże repo (wiele README, `apps/`, `optional-mcps/`).

## 2. Co robi przy instalacji

Paperclip:
- Zalecany instalator: `curl -fsSLO https://paperclip.ing/install.sh` + plik `.sha256` z tego samego origin, potem `bash install.sh` (`A/doc/INSTALLING.md:10-20`). Dokumentacja sama przyznaje, że suma kontrolna nie jest niezależnym dowodem autentyczności (`INSTALLING.md` ok. linii 33-37). Alternatywa: `npx paperclipai` (efemeryczny), instalacja globalna npm.
- Instalator pobiera Node.js (skrypty zewnętrzne przypięte i weryfikowane SHA-256, według dokumentacji) i może prosić o sudo.
- `Dockerfile`: `# syntax=docker/dockerfile:1.20`, `FROM node:24-trixie-slim` (tag, bez digestu; `Dockerfile:2`). `pnpm install --frozen-lockfile` po `--resolution-only` (`Dockerfile:~38`). Rustup przypięty wersją i SHA-256 (`Dockerfile:~66-79`).
- **Niepinowane**: `npm install --global --omit=dev @anthropic-ai/claude-code@latest @openai/codex@latest opencode-ai @google/gemini-cli@latest @moonshot-ai/kimi-code@latest` (`Dockerfile:~146`). Każdy build ściąga najnowsze CLI. To jest główna luka łańcucha dostaw w obrazie.
- `scripts/docker-entrypoint.sh`: start jako root, `chown -R node:node $PAPERCLIP_HOME`, potem `gosu node` (linie ~44-58).

Hermes:
- Zalecany: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` (`B/README.md:40`), Windows: jedna linia PowerShell (`README.md:43-61`). Czyli curl|bash bez sumy kontrolnej w README. Nie instaluj tak na maszynie z poświadczeniami.
- `Dockerfile`: baza `debian:13.4@sha256:e2d08da6...` (przypięta digestem), SQLite budowany ze źródeł z SHA-256 (`Dockerfile:1-30`), narzędzia przez własny `pm` z lockiem. Lepsza higiena niż Paperclip.
- Obraz ma `VOLUME /opt/data` (`Dockerfile:502`), `USER root` na etapie (`:368`), ENTRYPOINT `entrypoint-dispatch.sh` (`:536`), s6-overlay jako PID 1.

## 3. Klucze, pliki, telemetria, obce hosty

Paperclip:
- Zmienne: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` w compose (`A/docker/docker-compose.quickstart.yml:~25-27`). `BETTER_AUTH_SECRET` wymagany.
- Pliki poświadczeń: logowanie abonamentowe jest **izolowane** w katalogu sesji serwera (nie czyta Twojego `~/.claude`): `server/src/services/local-ai-credentials.ts:21` (`.credentials.json` z `loginHome`), `server/src/services/local-ai-browser-login.ts:116` (zapis `claudeAiOauth.accessToken` po `claude setup-token`, tryb 0600, `O_NOFOLLOW`), `server/src/services/device-login-credential-read.ts:47` (`auth.json` Codexa, odczyt bounded). UWAGA: adaptery mają też ścieżkę do prawdziwego katalogu domowego: `packages/adapters/claude-local/src/server/claude-config.ts:127` (`~/.claude`, gdy brak `CLAUDE_CONFIG_DIR`) i `codex-local/src/server/codex-home.ts:122` (`~/.codex`), `quota.ts` w obu. Dlatego w Dockerze nie montuj home.
- Telemetria: **domyślnie włączona**, wyłączana przez `DO_NOT_TRACK=1` lub `PAPERCLIP_TELEMETRY_DISABLED=1` (`packages/shared/src/telemetry/config.ts:71-76`; też auto-off w CI i `enabled:false` w pliku konfiguracji, `:77-82`). Hosty: `https://telemetry.paperclip.ing/ingest` i `https://rusqrrg391.execute-api.us-east-1.amazonaws.com/ingest` (`telemetry/client.ts:14-16`), nadpisywalne `PAPERCLIP_TELEMETRY_ENDPOINT`. Deklaracja: dane zanonimizowane (`A/releases/v2026.403.0.md:10`). Dodatkowo `PAPERCLIP_TELEMETRY_BACKEND_URL/TOKEN` w `server/src/config.ts:166-170` (nie badałem do czego służy).
- Inne obce hosty z kodu: `https://api.x.ai/v1/models` (weryfikacja loginu Grok, `local-ai-browser-login.ts:~124`), API dostawców, `paperclip.ing` (instalator).

Hermes:
- `~/.claude/.credentials.json` / Keychain i `~/.codex/auth.json` są czytane (pkt 4). Opis: `B/agent/credential_sources.py:12`, `:182-193`, `:263`.
- Własny `OAUTH_CLIENT_ID` `9d1c250a-e61b-44d9-88ed-5944d1962f5e` i tokeny przez `https://platform.claude.com/v1/oauth/token` (`B/agent/anthropic_credentials.py:36-44`).
- `iron_proxy.py:49-74` zawiera listę hostów dostawców i mapowanie zmiennych (`ANTHROPIC_API_KEY`, `XAI_API_KEY`, `NOUS_API_KEY`...). Hosty Nous: `inference-api.nousresearch.com`, `portal.nousresearch.com` (`agent/billing_view.py:320`, `anthropic_endpoints.py:112`).
- Telemetria: grep po `*.py`, `*.yaml` nie wykazał telemetrii produktu poza flagami innych narzędzi (np. `CUA_DRIVER_RS_TELEMETRY_ENABLED="0"`, `pm/packages.py:957`). Nie znaczy to, że nie ma jej w zależnościach i skillach. Obserwuj ruch wychodzący.

## 4. Abonament Claude/Codex bez klucza API i regulamin

Paperclip: uruchamia prawdziwe, oficjalne CLI (`claude`, `codex`) jako proces potomny; logowanie odbywa się samym CLI (`claude setup-token`, device login Codexa) w izolowanym katalogu. Dla Anthropic i OpenAI to wygląda jak zwykłe użycie ich klientów. Ryzyko regulaminowe niskie, ale: automatyzacja wielu agentów 24/7 na jednym abonamencie może wpaść w limity użycia lub zasady "uczciwego użycia". Sprawdź aktualne warunki planu.

Hermes: **tak, kod pożycza token OAuth Claude Code i podszywa się pod klienta Claude Code.** Dokładnie:
1. Odczyt: `B/agent/anthropic_credentials.py:340-355`. Ścieżka `${CLAUDE_CONFIG_DIR:-~/.claude}/.credentials.json` ("every profile reads/writes this same path"), plus macOS Keychain (docstring `:5`). Opt-out: `auth.adopt_external_logins: false` w `config.yaml`, **domyślnie `True`** (`B/hermes_cli/config_defaults.py:1760`).
2. Odświeżanie i zapis z powrotem: `_refresh_oauth_token` (`anthropic_credentials.py:467`) wysyła `refresh_token` z cudzym client_id Claude Code (`:36`, `:457`) do `platform.claude.com`; potem commit zaktualizowanych poświadczeń do `~/.claude/.credentials.json` (`:541`). Czyli może **zmieniać** plik Claude Code (ryzyko rozsynchronizowania rotowanych refresh tokenów z prawdziwym CLI).
3. Podszywanie: `B/agent/anthropic_adapter.py:238` dodaje nagłówki beta `claude-code-20250219`, `oauth-2025-04-20`; `:421-422` i `:507-508` ustawiają `user-agent: claude-code/<wersja> (external, cli)` oraz `x-app: cli`; `:318` wstrzykuje prefiks systemowy "You are Claude Code, Anthropic's official CLI for Claude."; `:540-566` przemianowuje nazwy narzędzi na `mcp__...`, z komentarzem, że single-underscore `mcp_` to "third-party-app fingerprint" kierowany do płatnego "extra usage" (HTTP 400); `:596` zamienia w prompcie slugi na `claude-code`.
4. Ocena: to jest obchodzenie mechanizmu, którym Anthropic rozróżnia klienta własnego od zewnętrznego. Z mojej wiedzy warunki Anthropic dla planów konsumenckich ograniczają tokeny OAuth do Claude Code/claude.ai, a Anthropic wprost egzekwował to wobec narzędzi trzecich. Ryzyko: blokada konta lub subskrypcji. Traktuj jako niezgodne, dopóki Anthropic nie potwierdzi inaczej.
5. Codex: Hermes czyta `~/.codex/auth.json` (`credential_sources.py:182`, `:263`) i ma własny device-flow `hermes auth add openai-codex`. Status regulaminowy OpenAI dla zewnętrznych klientów: do własnej weryfikacji.

Wniosek: Hermes z kluczem API Anthropic, OpenRouter, Nous itd. jest czysty. Hermes z tokenem Claude Code: nie.

## 5. Windows, Docker, porty, wolumeny

Paperclip:
- Natywny Windows: dokumentacja instalatora wymienia "macOS, Linux, or WSL2" (`INSTALLING.md:10`); usługi: systemd (Linux/WSL2) i LaunchAgent (`:197`). Natywnego Windows nie znalazłem jako wspieranej ścieżki instalacji. Wybór: WSL2 albo Docker Desktop.
- Docker: `A/Dockerfile`, `docker/docker-compose.yml` (Postgres `postgres:17-alpine`, port `3100:3100`), `docker-compose.quickstart.yml` (jeden kontener, wbudowana baza, `./data/docker-paperclip:/paperclip`, `HOST=0.0.0.0`), `docker-compose.untrusted-review.yml` (cap_drop ALL, no-new-privileges, tmpfs; ale też porty 3100 i 5173 na wszystkich interfejsach).
- Port: 3100 (domyślny `server/src/config.ts:321`), domyślny bind `127.0.0.1` poza kontenerem (`config.ts:194`). Wolumen: `/paperclip`.

Hermes:
- Natywny Windows (PowerShell), WSL2, Docker (`README.md:43-61`). `docker-compose.yml` oraz `docker-compose.windows.yml`.
- Compose: `network_mode: host`, wolumen `~/.hermes:/opt/data` (`docker-compose.yml:~45-50`), dashboard na 127.0.0.1 (komentarz w pliku), API server wyłączony dopóki nie ustawisz `API_SERVER_KEY`/`API_SERVER_HOST`. `network_mode: host` omija izolację sieci; w utwardzonej wersji niżej zastąpione.

## 6. Zadania, UI, budżety, heartbeat, effort/model, import organizacji

Paperclip:
- UI webowe (`A/ui`), zadania/projekty/komentarze, role i hierarchia agentów, zatwierdzenia przez "board".
- Budżet na agenta: `budgetMonthlyCents` (`packages/shared/src/validators/agent.ts:100`, domyślnie 0 = brak limitu; `:125` przy edycji). Specyfikacja: miękkie alerty i twarde auto-pause (`doc/SPEC-implementation.md:50`, `:1701`). Ustaw niezerowy budżet każdemu agentowi.
- Heartbeat: zegar harmonogramu serwera tyka co 30 s (`server/src/config.ts:363-364`, `HEARTBEAT_SCHEDULER_ENABLED`, `HEARTBEAT_SCHEDULER_INTERVAL_MS`, min 10 s). Timerowy heartbeat agenta jest **domyślnie wyłączony**: `enabled=false`, `intervalSec=0` (`server/src/services/heartbeat/queue.ts:396-397`), więc sam nie pali tokenów w ciszy. **Uwaga:** import z paczki agentcompanies ustawia domyślnie `heartbeat.intervalSec = 3600` (`server/src/services/company-portability.ts:789`), czyli zaimportowani agenci mogą budzić się co godzinę. Sprawdź po imporcie.
- Model i effort per agent: adapter Claude przyjmuje `effort` (`low|medium|high`, nowsze modele także `xhigh|max`) przez `--effort` (`packages/adapters/claude-local/src/index.ts:67`); Codex `modelReasoningEffort` i `model` (`codex-local/src/server/codex-args.ts:~83`); `model` jest w konfiguracji adaptera.
- Import schematu organizacji: format agentcompanies (`agentcompanies/v1`): pliki `COMPANY.md`, `TEAM.md`, `AGENTS.md`, `PROJECT.md`, `TASK.md`, `SKILL.md` + sidecar `.paperclip.yaml`; spec w `A/docs/companies/companies-spec.md`, implementacja `server/src/services/company-portability.ts:4106` (eksport/import/podgląd), indeks `doc/AGENTCOMPANIES_SPEC_INVENTORY.md`. Zaimportowane skille i polecenia są kodem/promptami z zewnątrz: przejrzyj przed importem.

Hermes (skrótowo): to pojedynczy agent z gateway'em (Telegram/Teams/Google Chat itd.), cron (`B/cron`), brak modelu "firmy" i budżetów per agent jak w Paperclip.

## 7. Ryzyka

Paperclip:
- **Domyślnie bez sandboxa i z pominięciem zgód**: Claude `dangerouslySkipPermissions` domyślnie `true` (`claude-local/src/server/execute.ts:440`, `permissions.ts:12` dodaje `--dangerously-skip-permissions`); Codex dodaje `--dangerously-bypass-approvals-and-sandbox` (`codex-args.ts:80`) gdy domyślna stała bypass jest włączona i brak jawnych ograniczeń (`:62-63`); OpenCode `dangerouslySkipPermissions` domyślnie `true` (`opencode-local/src/server/runtime-config.ts:110`). W praktyce agenci wykonują dowolne polecenia z uprawnieniami użytkownika kontenera. Dlatego kontener bez home i z limitami to minimum.
- Obraz zawiera `gh`, `git`, `curl`, `openssh-client` (`Dockerfile:6`, `:147`), więc zwykły wyciek tokenu do kontenera = wyciek na GitHub/SSH. Nie przekazuj GITHUB_TOKEN ani kluczy SSH.
- Niepinowane `@latest` CLI (pkt 2). Brak auto-aktualizacji samego serwera w kodzie, który znalazłem (instalator ma zarządzane aktualizacje i rollback, `INSTALLING.md:1-5`).
- Publiczny port: tryb `authenticated` + `PAPERCLIP_DEPLOYMENT_EXPOSURE=private`; `local_trusted` pomija autoryzację. Quickstart mapuje `3100` na wszystkich interfejsach hosta i `HOST=0.0.0.0`.
- Telemetria domyślnie włączona.

Hermes:
- `--yolo` / `HERMES_YOLO_MODE=1` pomija zatwierdzanie niebezpiecznych poleceń (`B/hermes_cli/main.py:1767`, `:2936`); w `cli-config.yaml.example` są ustawienia zatwierdzeń.
- `network_mode: host`, wolumen `~/.hermes` ze wszystkimi kluczami (dashboard "stores API keys").
- `adopt_external_logins: True` domyślnie (kradzież/pożyczka tokenów z `~/.claude`, `~/.codex`).
- Instalator curl|bash; polecenie `hermes update` (`hermes_cli/update_cmd_commit.py`) aktualizuje kod z sieci, a sprawdzanie aktualizacji jest uruchamiane w tle (`main.py:1613-1626`).
- Wykonuje polecenia i uruchamia Chromium (Playwright) w obrazie; wiele integracji MCP (`optional-mcps/`).

## 8. Konfiguracja Docker Compose

### 8a. Paperclip: `deploy/paperclip/docker-compose.yml`

Plik jest w repozytorium (walidacja YAML przeszła; **nie budowałem ani nie uruchamiałem obrazu** zgodnie z zakazem). Założenia i spełnienie wymagań:
- osobny użytkownik: UID/GID 10001 (`USER_UID/USER_GID` jako build args; entrypoint schodzi `gosu` na `node`). Start jako root jest wymagany przez `docker-entrypoint.sh` (chown woluminu), potem proces jedzie jako nie-root; capabilities zawężone do CHOWN/SETUID/SETGID/DAC_OVERRIDE. Gdyby start nie przeszedł, sprawdź logi i ew. dodaj `FOWNER`;
- bez home: jedyny wolumen to nazwany `paperclip-data:/paperclip`;
- `DO_NOT_TRACK=1`, `PAPERCLIP_TELEMETRY_DISABLED=1`;
- przypięte: źródła do commita `bfe7c63...`, obraz taguje się `paperclip-local:bfe7c63`. **Niedomknięte**: baza `node:24-trixie-slim` bez digestu i CLI `@latest` w `Dockerfile`. Aby domknąć, skopiuj `Dockerfile` do forka, zmień `FROM` na digest i wpisz konkretne wersje `@anthropic-ai/claude-code@X @openai/codex@Y` (wersje do ustalenia po stronie operatora);
- limity: `cpus: 2`, `mem_limit: 4g`, `pids_limit: 1024`;
- port `127.0.0.1:3100:3100`.
- Egress nie jest ograniczony (Compose nie filtruje po domenie). Dla twardszej izolacji użyj reguł zapory hosta lub proxy z allowlistą (`api.anthropic.com`, `api.openai.com`, `github.com` jeśli potrzebne).

Komendy:
```
cd deploy/paperclip
export BETTER_AUTH_SECRET="$(openssl rand -hex 32)"
docker compose build --pull
docker compose up -d
docker compose logs -f paperclip
# UI: http://127.0.0.1:3100  (z innej maszyny: ssh -L 3100:127.0.0.1:3100 host)
# logowanie abonamentem: w UI, ekran połączeń AI (izolowany login zapisze się w wolumenie)
docker compose down        # zatrzymanie; dane zostają w wolumenie paperclip-data
```
Po pierwszym uruchomieniu: ustaw `budgetMonthlyCents` dla każdego agenta, sprawdź heartbeat (`intervalSec`), wyłącz `dangerouslySkipPermissions` tam, gdzie agent nie jest w pełni zaufany.

### 8b. Hermes minimalnie, bez dostępu do poświadczeń Claude

Nie zapisałem tego jako osobny plik (zadanie wskazywało tylko jeden). Szkic do `deploy/hermes/docker-compose.yml`, **nie testowany**:
```yaml
name: hermes
services:
  hermes:
    build:
      context: https://github.com/NousResearch/hermes-agent.git#1fd18277267152893a8a24792b79213e7ca3f899
    image: hermes-local:1fd1827
    command: ["gateway", "run"]
    restart: unless-stopped
    init: true
    cpus: "2.0"
    mem_limit: 4g
    pids_limit: 512
    security_opt: ["no-new-privileges:true"]
    cap_drop: [ALL]
    cap_add: [CHOWN, SETUID, SETGID, DAC_OVERRIDE]   # s6-overlay + usermod; zawęź po testach
    # brak network_mode: host, brak ports (gateway wychodzi do komunikatorów sam)
    # ports: ["127.0.0.1:8642:8642"]   # tylko jeśli włączasz API server; ustaw też API_SERVER_KEY
    environment:
      HERMES_UID: "10002"
      HERMES_GID: "10002"
      DO_NOT_TRACK: "1"
      # Jawny klucz API zamiast tokenu abonamentowego (wstaw ze swojego .env, nie z ~/.claude):
      ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:?}"
    volumes:
      - hermes-data:/opt/data       # NIE ~/.hermes, NIE ~/.claude, NIE ~/.codex
volumes:
  hermes-data:
```
Dodatkowo w `/opt/data/config.yaml` ustaw `auth.adopt_external_logins: false` (`config_defaults.py:1760`, nazwa klucza z komentarza w kodzie; zweryfikuj po starcie). Nie używaj `--yolo`. Port API (jeśli w ogóle) tylko na 127.0.0.1 z `API_SERVER_KEY`.

## Otwarte punkty do sprawdzenia przez człowieka
1. Aktualne warunki Anthropic i OpenAI dla użycia abonamentów przez zewnętrzne narzędzia.
2. Co robi `PAPERCLIP_TELEMETRY_BACKEND_URL/TOKEN` (`server/src/config.ts:166-170`).
3. Rzeczywisty ruch sieciowy obu aplikacji (nie uruchamiałem żadnej).
4. Wersje CLI do przypięcia w Dockerfile Paperclip.
