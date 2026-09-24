# Przekazanie frontendu — spin.clinic

## Punkt startowy

Gałąź do pracy: `codex/mvp-public-frontend`.

Projekt jest monorepo. Publiczny frontend działa w `frontend-spin`, a wspólne
komponenty i typy znajdują się w `packages/ui`.

Najważniejsze widoki:

- strona główna: `frontend-spin/app/page.tsx`;
- wspólny układ i style: `frontend-spin/app/layout.tsx`,
  `frontend-spin/app/globals.css`;
- komponenty strony głównej: `packages/ui/src/components`;
- strony informacyjne: `frontend-spin/app/o-nas`, `zrodla`, `wsparcie`,
  `polityka-prywatnosci`, `zasady-korzystania`, `dostep`;
- panel redakcyjny X: `frontend-spin/app/editor/political/page.tsx` i
  `packages/ui/src/components/PoliticalReview.tsx`.

## Uruchomienie lokalne

1. Sklonuj repozytorium i przełącz się na tę gałąź.
2. Skopiuj `.env.example` jako `.env`.
3. Pozostaw wszystkie integracje zewnętrzne wyłączone, jeżeli nie masz
   własnych kluczy. Kluczy nigdy nie zapisuj w Git.
4. Uruchom backend i usługi danych przez Docker Compose. Backend wykonuje
   migracje przy starcie.
5. W drugim terminalu uruchom `pnpm install --frozen-lockfile`, a następnie
   `pnpm dev:spin`. Frontend Next.js domyślnie działa pod
   `http://localhost:3000`; lokalny port może zostać zmieniony świadomie przy
   uruchamianiu.

## Granice pracy

- Nie dodawaj kluczy API, `.env`, danych bazy ani wyników pobierania do Git.
- Nie zmieniaj automatycznie pobierania X, publikacji materiałów ani ustawień
  Dockera bez osobnego uzgodnienia.
- Integracje X, YouTube, NVIDIA NIM i Groq mają pozostać wyłączone domyślnie.
- Wyniki AI są wyłącznie szkicami redakcyjnymi do ręcznego zatwierdzenia.

## Stan danych

Lokalna baza danych nie jest częścią repozytorium. Po czystym uruchomieniu
dostępne są migracje, modele, panel administracyjny oraz źródła testowe, ale
nie prywatne klucze ani lokalnie zaimportowane dane redakcyjne.

## Kontrola przed przekazaniem zmian

Uruchom testy backendu i build frontendu w lokalnym środowisku. W razie zmian
wizualnych sprawdź stronę główną w układzie desktopowym i mobilnym oraz trzy
motywy: ciemny, jasny i pastelowy.
