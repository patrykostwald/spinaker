# Audyt spin.clinic po wycięciu spinek (9.10.2026)

Zakres: tylko odczyt repo (gałąź codex/mvp-public-frontend) i jedno zapytanie do https://spin.clinic oraz odczyty publicznych adresów. Nic nie zmieniono, nic nie wdrożono. Nie czytano .env ani kluczy. Odwołania: plik:linia (ścieżki względem korzenia repo).

## 0. Najważniejsze wnioski (6 zdań)

1. Produkcja ma dziś włączone spinki: https://spin.clinic/ pokazuje listę spinek (zakładki Wszystkie, Dr. Spin, Czytelnicy, Izba przyjęć, „Ułóż swoją spinkę”), lewy pasek zaczyna się od „Spinki”, a /spinki odpowiada 200 (zrzuty 9.10).
2. Spinki to nie dodatek: cała powłoka serwisu zależy od jednej flagi THREADS_ENABLED (`packages/ui/src/lib/features.ts:6,26`; backend `backend/config/settings.py:305`, domyślnie False; `deploy/docker-compose.production.yml:28`, domyślnie false). Przy fladze włączonej nawigację, pasek kategorii i stronę główną rysują SocialNavigation, SectionBar i HomeThreads; przy wyłączonej wraca stary SiteHeader i prosta główna (`packages/ui/src/components/SiteHeader.tsx:32,38`, `packages/ui/src/kit/home/HomePage.tsx:26,42`, `packages/ui/src/components/community/SocialNavigation.tsx:60,70`, `packages/ui/src/components/community/SectionBar.tsx:25,47`).
3. Główna to dziś kanał „spinek” utworzonych automatycznie z diagnoz i przekazów dnia (3 publiczne wiersze: 2 przekazy dnia, 1 diagnoza; zero od czytelników; GET /api/community/threads/). Po wycięciu spinek główna musi dostać nową treść z diagnoz, przekazów i wywiadów, bo flaga false daje tylko wyjaśnienie spinu, zapowiedź i newsletter (`HomePage.tsx:42`).
4. Komentowanie diagnoz i wywiadów już istnieje (model ClinicComment, API, UI, moderacja, limity), ale nie obejmuje przekazów dnia, a liczniki w kartach są wyłączone stałą SHOW_DISCUSSION_COUNTS=false (`packages/ui/src/components/clinic/ClinicDiscussion.tsx:24`).
5. Zalążek alertów o wpisach polityków istnieje (Follow z trybem „każdy wpis”, outbox zdarzeń, web push z VAPID, PWA z service workerem, a produkcja zwraca push enabled=true), ale „błyskawiczność” ogranicza odpytywanie X co najmniej 5 do 15 minut, okno grupowania 15 minut i cisza nocna 23:00-07:00 oraz koszt X (5 USD/mies. domyślnie).
6. Zależności danych są twarde: PersonalContextThread ma OneToOne z SpinDiagnosis i ClinicDailyMessage (CASCADE), a sygnał na zapis diagnozy tworzy spinkę automatycznie (`backend/news/signals.py:36-39`); usunięcie modelu bez wcześniejszego odpięcia sygnałów zepsuje zapis diagnoz.

## A. Tabela: co usunąć, co ukryć, co zachować

Legenda: USUŃ = wycięcie z produktu (kod i trasy, po archiwizacji danych); UKRYJ = zostaje w kodzie, wyłączone flagą lub bez linków (zamrożenie pod osobny produkt); ZACHOWAJ = zostaje.
Uwaga o nazwie: w repo są dwa różne „wątki”: (1) `news.Thread`/ThreadItem (stary model redakcyjny, strona /thread/[slug], ThreadFavorite, ThreadOpinion) oraz (2) `PersonalContextThread` (spinki użytkowników i automatyczne spinki Dr. Spina). Wycięcie dotyczy głównie (2); (1) wymaga osobnej decyzji (pytanie 6).

### A1. Frontend: powłoka, nawigacja, strona główna

| Miejsce | Dziś | Po wycięciu |
|---|---|---|
| `packages/ui/src/lib/features.ts:6,26` | flaga THREADS_ENABLED z NEXT_PUBLIC_THREADS_ENABLED | UKRYJ jako pierwszy krok (false); docelowo USUŃ flagę |
| `packages/ui/src/components/community/SocialNavigation.tsx` (pozycja „Spinki” `:24`, zwraca null przy fladze false `:60`) | lewy pasek, dolny pasek telefonu, dzwonek | USUŃ „Spinki”; przenieść konto, powiadomienia, szukaj do nowego menu; przepisać, bo to jedyna nawigacja przy fladze true |
| `packages/ui/src/components/community/SectionBar.tsx:25-31,47,59-62,77-85` | zakładki źródeł spinek, „Ułóż swoją spinkę”, sortowanie spinek; ustawia html[data-view] z kolorami tła | USUŃ gałąź „tropy”; ZACHOWAJ gałąź klinika/konsylium/o-nas (to nawigacja Kliniki: `clinicNavigation`) |
| `packages/ui/src/components/SiteHeader.tsx:32,38` | zwraca null przy spinkach | ZACHOWAJ (to nawigacja po wyłączeniu); wymaga przeglądu designu |
| `frontend-spin/app/layout.tsx:50` | `sc-social-layout` z SocialNavigation i SectionBar | przepisać layout |
| `packages/ui/src/kit/home/HomePage.tsx:26,37-42` | HomeThreads albo fallback; h1 „Diagnozy Dr. Spina i spinki” | USUŃ gałąź spinek; zmienić h1; nowa główna (patrz sekcja E) |
| `packages/ui/src/kit/home/HomeThreads.tsx:13,21`, `HomeDrSpin.tsx:5-114` | feed i pas „Spinka Dr. Spina” z tekstami „Tropy”, „Wkrótce własne spinki ułożą też czytelnicy” | USUŃ (HomeDrSpin: sprawdzić, czy jest jeszcze montowany) |
| `packages/ui/src/kit/home/data.ts:184-209` | spinka demonstracyjna i „Trop Dr. Spina” | USUŃ |
| `packages/ui/src/kit/home/HomeSpinTeaser.tsx`, `HomeSupport.tsx`, `SpinExplainer`, `NewsletterSignup` | fallback głównej | ZACHOWAJ (baza nowej głównej) |
| `frontend-spin/app/PreviewControls.tsx:23-24` | dolny pasek gdy brak spinek | ZACHOWAJ; sprawdzić |
| `frontend-spin/app/manifest.ts:26` | skrót „Spinki” → /spinki | USUŃ skrót; opis `:7` OK |
| `frontend-spin/app/PwaControls.tsx:9,146` | temat push „Spinki Dr. Spina” (`nitki-dr-spina`), tekst „Klinika i spinki pod ręką” | USUŃ temat i tekst; zmiana tematów wymaga migracji subskrypcji (backend `news/push.py:9` TOPICS) |
| `frontend-spin/app/FirstVisitIntro.tsx:7`, `frontend-spin/public/jak-dziala/index.html` (9 trafień „spink/nitk/thread”) | film 60 s na wejściu | ZACHOWAJ mechanizm; przerobić treść filmu (wzmianki o spinkach) |
| `frontend-spin/app/podglad/page.tsx:20` | link „Spinki czytelników” | USUŃ |

### A2. Frontend: trasy i komponenty spinek

| Miejsce | Po wycięciu |
|---|---|
| `frontend-spin/app/spinki/page.tsx`, `spinki/[id]/page.tsx`, `spinki/odwolanie` | USUŃ; zostawić przekierowanie 301/410 (patrz D) |
| `frontend-spin/app/konto/spinki/nowa`, `konto/spinki/[id]` | USUŃ, przekierować do /konto (już dziś `redirect('/konto')` przy fladze false) |
| `frontend-spin/app/thread/[slug]/page.tsx` (ThreadView, ThreadOpinions, ThreadFavoriteButton, ShareThreadOnX, ThreadExport) | to stary model news.Thread; UKRYJ do decyzji (pytanie 6) |
| `frontend-przeszlosc/app/thread/[slug]/page.tsx`, `frontend-przeszlosc/app/editor/page.tsx` | osobna aplikacja; sprawdzić odwołania do wspólnego pakietu ui |
| `frontend-spin/app/dla-redakcji/ContextThreadExample.tsx` (przykład „Autoryzowana spinka”) | USUŃ z oferty dla redakcji; zastąpić próbką raportu |
| `frontend-spin/app/en/press/page.tsx:4` („join the authorised context thread pilot”) | USUŃ zdanie |
| `packages/ui/src/components/community/*` (ThreadOverlay, ThreadSocial, ThreadSteps, ThreadStrip, ThreadFeed, ThreadMeta, ThreadModerationPanel, RepinPanel, CommunityPages, ThreadAppealPage, SectionBar, SocialNavigation) | USUŃ z montowania; kod ZAMROZIĆ w osobnym katalogu/gałęzi pod produkt spinek |
| `packages/ui/src/components/MojaNitkaEditor.tsx`, `ThreadEditor.tsx`, `ThreadCard.tsx`, `ThreadExport.tsx`, `ThreadFavoriteButton.tsx`, `ThreadOpinions.tsx`, `OpinionsPanel.tsx`, `ShareThreadOnX.tsx`, `JournalistInvite.tsx`, `kit/ThreadView.tsx`, `lib/threadKind.ts`, `lib/community.ts`, `lib/spinkaExport.ts`, `lib/xStory.ts`, `lib/clipColor.ts` | USUŃ z eksportów `packages/ui/src/index.ts` (10 trafień); ZAMROZIĆ |
| `packages/ui/src/components/ContextThreadStrip.tsx` (sekcja „W spinkach” na diagnozie, `:35`; montowana w SpinDetail) | USUŃ (na zrzucie diagnozy jest pusty box „Nie ma jeszcze publicznych spinek”) |
| `packages/ui/src/components/FollowButton.tsx:14-15` | ZACHOWAJ (obserwowanie osób, kluczowe dla alertów); usunąć ścieżkę `kind==='thread'` |
| `packages/ui/src/components/MojeKonto.tsx` (17 trafień), `AccountDashboardParts.tsx`, `AccountProfile.tsx`, `AccountPhase2.tsx:50,106,147`, `PublicSocialProfile.tsx`, `AccountDialog.tsx:52,65` | przepisać: usunąć karty „Twoje spinki”, „opublikowane spinki”, ocenę „zmienia kolor spinki”; ZACHOWAJ aktywność, obserwowanych, powiadomienia |
| `packages/ui/src/lib/personal.ts:102-107` | usunąć zapytania o spinki własne |
| `packages/ui/src/components/PrzekazDnia.tsx`, `DrSpin.tsx`, `clinic/WeeklyReport.tsx`, `clinic/ShareSpinOnX.tsx`, `PublicFigureProfile.tsx`, `MaterialDetails.tsx`, `SourcesCatalog.tsx` | po kilka wzmianek, sprawdzić linki do /spinki i /thread |
| `packages/ui/src/kit/kit.css` (801 trafień „thread/spink”), `frontend-spin/app/globals.css` (26) | wyciąć style po usunięciu komponentów |
| `packages/ui/src/kit/showcase/sections/Thread.tsx`, `ui-kit` | USUŃ z katalogu kitu |

### A3. Teksty i prawo (do usunięcia wzmianek)

| Plik | Co |
|---|---|
| `frontend-spin/app/polityka-prywatnosci/page.tsx:9,10,12` | „Zapisujemy Twoje spinki…”, „opublikowane spinki są publiczne”, „komentarze pod spinkami”, „ze spinki do diagnozy” |
| `frontend-spin/app/zasady-korzystania/page.tsx:17-28` (sekcja `#tropy`: limity tytułu 65/170/200 znaków, komentarz 280/2000, @b3/@s2, oceny połączeń ✕ ? ✓, punktacja) | USUŃ sekcję; zostawić zasady komentarzy pod diagnozami i wywiadami |
| `frontend-spin/app/zasady-dyskusji/page.tsx:20-21` | usunąć sekcję „Spinki”, link `#tropy` |
| `frontend-spin/lib/documents/AboutDocument.tsx`, `PressDocument.tsx`, `english.ts` | wzmianki; przepisać |
| `frontend-spin/app/konto/page.tsx:8` | opis „Twoje spinki…” |
| `frontend-spin/next.config.js:19-26` | przekierowania /nitki, /tropy, /konto/nitki, /konto/tropy → /spinki; ZMIENIĆ cel na /klinika lub /; nie zostawiać łańcucha przez usuniętą trasę |
| Ciąg „Wiadomości · Klinika · Nitki” | w kodzie i plikach repo nie znaleziono tego dosłownego napisu (znaleziony tylko w pamięci projektu); działy faktyczne to Spinki, Klinika, Szukaj, Profil, Powiadomienia (zrzut 1440) |

### A4. Backend: modele i klucze obce (zależności, które się rozsypią)

| Obiekt | Plik:linia | Zależność / ryzyko |
|---|---|---|
| PersonalContextThread | `backend/news/account_models.py:106`; OneToOne `diagnosis` (`:17` w klasie), `narrative_message` (OneToOne do ClinicDailyMessage, CASCADE), CheckConstraint z 4 wariantami pochodzenia | usunięcie modelu = migracja z 33 plikami migracji powiązanymi z „thread”; CASCADE od SpinDiagnosis i ClinicDailyMessage (kasowanie diagnozy kasuje spinkę, nie odwrotnie) |
| PersonalContextThreadItem | `account_models.py:172` | kaskada z wątku |
| Follow.thread (FK) + CheckConstraint | `backend/news/notification_models.py:11,17-19` | trzeba migracji zmieniającej CheckConstraint „dokładnie jeden cel” (figure, target_user, thread) i UniqueConstraint `unique_follow_thread`; Follow.figure (obserwowanie osób) ZACHOWAĆ |
| NotificationSettings.push_thread_replies | `notification_models.py:38`, `notification_api.py:125`, `notify.py:32`, `account_lifecycle.py:271` | pole do wygaszenia; UI `AccountPhase2.tsx:147` |
| ThreadComment, ThreadCommentReaction, ThreadRateEvent, ThreadModerationReport/Decision/Mail, ThreadStepReaction | `backend/news/thread_social_models.py:7-85` | FK do PersonalContextThread (CASCADE lub SET_NULL); ThreadModerationDecision używa PROTECT (`:61`) wobec zgłoszenia, co blokuje kasowanie zgłoszeń z decyzjami |
| CommunityLink, CommunityThreadOpinion, CommunityThreadReport | `backend/news/community_models.py:14,35,56` | oceny spinek; CommentReport ma wspólną tabelę z komentarzami artykułów (`account_models.py:204`; CheckConstraint wymaga article_opinion XOR thread_opinion) |
| ThreadReview, ThreadReviewRound | `backend/news/thread_review_models.py:5-29`; import w `news/models.py:8` | OneToOne do PersonalContextThread i news.Thread; import w models.py trzeba zdjąć razem z migracją |
| news.Thread, ThreadItem (stary model redakcyjny) | `news/models.py:644,716` | używany także przez `portal.py:184-193` (edycje „government/opposition”), `views.py:165-182`, `profiles.py:12-139` (ThreadFavorite), admin `admin.py:123-188`; osobna decyzja |
| ThreadOpinion, ThreadFavorite | `account_models.py:38,86` | FK do news.Thread (nie do spinek); dane „ulubione” do archiwizacji |
| Sygnały | `backend/news/signals.py:36-39` (każdy zapis SpinDiagnosis woła `sync_diagnosis_thread`), `:42-75` (thread_text_changed na Thread, ThreadItem, PersonalContextThread) | NAJPIERW odpiąć sygnały, potem usuwać modele; inaczej zapis diagnozy rzuci błąd |
| API | `backend/news/urls.py:3-4,24,34,51,55,87-99` (`community/threads/…`, komentarze, reakcje, moderacja, karta PNG, kroki, `editor/threads`, `threads`) | USUŃ trasy po zamrożeniu; `community/moderation/` i `reports/` też |

### A5. Backend: zadania harmonogramu i polecenia

Harmonogram: `backend/news/daily_schedule.py` (wpisy `:12,13,37,38,54`; kamienie milowe `:294-312`) oraz `backend/config/celery.py:20` (thread-moderation-mail co minutę).

| Zadanie | Gdzie | Po wycięciu |
|---|---|---|
| narrative-thread-daily 21:45 i retry 22:00/22:15 | `daily_schedule.py:37-38`, `tasks.py:467` | USUŃ |
| signal-threads-daily 22:20 | `daily_schedule.py:12`, `tasks.py:473` (sygnały lobbingu, nowe narracje) | USUŃ lub UKRYJ (pytanie 7: sygnały lobbingu to osobna wartość B2B) |
| thread-reviews-20m (Kontrola spinek) | `daily_schedule.py:13`, `tasks.py:479`, `thread_review.py` | USUŃ |
| dr-spin-thread-daily 19:30 | `daily_schedule.py:54`, `tasks.py:370`, `dr_spin_threads.py`, flaga DR_SPIN_THREADS_ENABLED | USUŃ |
| thread-moderation-mail co minutę | `celery.py:20`, `notification_tasks.py` | USUŃ po opróżnieniu kolejki (ryzyko D3) |
| Kamienie milowe w raporcie planu dnia: „Spinka narracji”, „Spinka Dr. Spina” | `daily_schedule.py:226-243,294-312` | USUŃ; inaczej raport planu dnia pokaże wieczne „czeka na opracowanie” (przy fladze false pokazuje „na”) |
| Polecenia | `management/commands/dr_spin_thread.py`, `drspin_diagnosis_threads.py`, `drspin_narrative_threads.py`, `drspin_review_threads.py`, `drspin_signal_threads.py`, `drspin_refresh_all.py` (24 trafień), `requeue_rejected_threads.py`, `thread_moderation_mail.py`, `clinic_x_threads.py`, `fill_x_threads.py` | uwaga: `clinic_x_threads` i `fill_x_threads` dotyczą wątków na X (`tasks.py:128-132`, `clinic.py`), nie spinek; ZACHOWAĆ po sprawdzeniu |
| Rejestr agentów | `agent_registry.py:43-46,77` (moderation-mail, narrative-threads, signal-threads, thread-review, spin-thread) | USUŃ wpisy; zasila panel centrum |
| Strażnik „Spinki: główna jest pusta” | `duty_extra.py:96-109,135` (alarm critical `threads:empty`) | USUŃ razem z funkcją; inaczej alarm na głównej |
| Admin | `community_admin.py:21-72`, `thread_social_admin.py:27-81`, `admin.py:21-22,123-188`, `templates/admin/dashboard.html`, `index.html` | UKRYJ/USUŃ |
| Konto: eksport i usuwanie | `account_lifecycle.py:240-290,315-329` (eksport zawiera spinki, komentarze, oceny; kasowanie czyści powiadomienia `/spinki`, `/tropy`, `/nitki`) | po wycięciu pola w eksporcie danych osobowych (RODO) muszą nadal obejmować archiwum, dopóki dane istnieją |
| Pulpit konta | `account_dashboard.py:16-123,152-178` | usunąć sekcje spinek; ZACHOWAĆ aktywność i powiadomienia |
| Testy | 19 plików backend (m.in. `test_thread_social.py` 125 trafień, `test_diagnosis_threads.py` 96, `test_thread_signals_091.py`, `test_dr_spin_threads.py`, `test_social_087.py`, `test_community*.py`, `test_personal_context.py`, `test_account_dashboard.py` 45, `test_notifications.py` 42, `test_account_lifecycle.py`, `test_preview.py`); frontend: `tests/thread-social.browser.cjs`, `social-087.browser.cjs`, `account-dashboard.browser.cjs`, `preview.test.cjs:27,57-61` | usunąć lub przepisać; testy powiadomień i konta mieszają spinki z diagnozami (np. `test_notifications.py:21`), więc nie kasować hurtem |

### A6. Co ZACHOWAĆ (i dopracować)

| Funkcja | Pliki |
|---|---|
| Diagnozy, przekazy dnia, wywiady, raporty | `frontend-spin/app/klinika/*`, `packages/ui/src/components/clinic/*`, `backend/news/clinic*.py`, `clinic_models.py` (SpinDiagnosis, ClinicDailyMessage `:190`, ClinicInterview `:263`, WeeklyReport `:314`) |
| Komentarze i oceny diagnoz i wywiadów | `clinic_discussion.py`, `clinic_discussion_models.py:11-68` (ClinicComment, ClinicCommentReport, InterviewOpinion), `clinic_moderation.py`, `clinic_discussion_admin.py`, `SpinOpinion` (`clinic_models.py:225`, dane starszych reakcji), `ClinicDiscussion.tsx` |
| Obserwowanie osób i powiadomienia | `notification_models.py` (Follow.figure, Notification, NotificationPost, NotificationEvent), `followed_posts.py`, `notification_tasks.py` (gałąź `diagnosis`), `FollowButton.tsx`, `PublicFigureProfile.tsx:502` |
| Push i PWA | `push.py`, `push_api.py`, `push_events.py`, `push_models.py`, `frontend-spin/public/sw.js`, `PwaControls.tsx`, `manifest.ts` |
| Alerty e-mail przeszłość.today | `przeszlosc_alerts.py`, `frontend-spin/app/przeszlosc/alerty` |
| Konta, e-mail, newsletter, raporty dla instytucji | `account*.py`, `NewsletterSignup.tsx`, `dla-redakcji/InstitutionReports.tsx`, `report_*.py` |
| Ulubione artykułów | `ArticleFavorite` (`account_models.py:96`), `ArticleOpinion` (`:23`) niezależne od spinek |

## Dane do archiwizacji (liczby)

Bez dostępu do produkcji i bazy. Wartości z publicznego API w dniu audytu (GET https://spin.clinic/api/community/threads/):
- publicznych spinek w feedzie: 3 (2x przekaz dnia, 1x diagnoza), wszystkie „Dr. Spin (AI)”, zero od czytelników (`author_id` puste), zero komentarzy w sumie na tej stronie wyników;
- największy identyfikator spinki: 98 (górne oszacowanie liczby utworzonych wierszy PersonalContextThread, razem z ukrytymi i odrzuconymi);
- liczby opinii, ulubionych (ThreadFavorite), komentarzy (ThreadComment), obserwowań wątków (Follow.thread), subskrypcji push na temat `nitki-dr-spina`, zgłoszeń moderacji i kolejki ThreadModerationMail: NIEZNANE z kodu (testy używają danych syntetycznych); zebrać zapytaniami COUNT na serwerze (pytanie 3).
Dane do eksportu przed wycięciem: PersonalContextThread i Item, ThreadComment i reakcje, ThreadRateEvent, ThreadStepReaction, CommunityThreadOpinion/Report/Link, ThreadReview i rundy, ThreadModerationReport/Decision/Mail, ThreadOpinion, ThreadFavorite, Follow.thread. Nie archiwizować treści prywatnych spinek poza zakresem zgody (polityka: `polityka-prywatnosci/page.tsx:10` obiecuje, że prywatne spinki nie są publiczne).

## B. Luki względem nowego kierunku (wg wagi)

Szacunek: S = do 1 dnia, M = 2-5 dni, L = ponad tydzień (praca jednego agenta z testami i pętlą designu).

### Krytyczne

| # | Luka | Dowód | Praca |
|---|---|---|---|
| K1 | Nie ma planu bezpiecznego wycięcia: sygnał diagnoza → spinka, OneToOne do diagnoz i przekazów, Follow.CheckConstraint, wspólna tabela CommentReport | `signals.py:36-39`; `account_models.py:17`; `notification_models.py:17-19`; `account_models.py:204-225` | M (kolejność: odpięcie sygnałów i zadań, flaga false, eksport, migracje) |
| K2 | Główna po wycięciu: flaga false daje tylko wyjaśnienie, zapowiedź Kliniki i newsletter, bez przekazów dnia, diagnoz i wywiadów (te są dziś w Klinice) | `HomePage.tsx:42`; zrzut Kliniki 1440 | M |
| K3 | „Błyskawiczne” alerty o wpisach polityków: opóźnienie wynika z odpytywania X co 5-15 min dla obserwowanych (`political_polling.py:46-47,219-220`), cichych godzin 23-07 (`followed_posts.py:48`, `push_events.py:41-42`), okna grupowania 15 min (`followed_posts.py:13`), limitów kosztu (domyślnie 100 wpisów i 100 żądań dziennie, 5 USD miesięcznie, `political_polling.py:48-50`) i flagi X_POLITICAL_POLLING_ENABLED; nie ma żadnego kanału push z X w czasie rzeczywistym | j.w. | L (decyzja o źródle i budżecie; pytanie 4) |
| K4 | Przekazy dnia nie mają komentarzy: ClinicComment ma cel tylko diagnoza XOR wywiad (CheckConstraint), a routy tylko `spins` i `interviews` | `clinic_discussion_models.py:45-47`; `urls.py:145-150`; `MessageDetail.tsx` bez ClinicDiscussion | M (nowy cel w modelu, migracja, API, UI, testy; można użyć istniejącej moderacji) |
| K5 | Dokumenty prawne mówią o spinkach (do usunięcia) i o komentarzach w sposób mieszany; po wycięciu zasady komentarzy diagnoz muszą stać samodzielnie. Prawnik musi przejrzeć | A3 | S-M |

### Ważne

| # | Luka | Dowód | Praca |
|---|---|---|---|
| W1 | Komentarze: liczniki i oceny w kartach wyłączone stałą (właściciel 5.10 „później”); brak powiadomień do autora diagnozy/administracji o nowych komentarzach, jest tylko powiadomienie o odpowiedzi na komentarz (`notify_reply`), brak sortowania i zwijania wątków, brak limitów per cel (są globalne: 30 s, 10 na godzinę, 50 na dobę), moderacja zależy od bezpłatnego Groq (`MEMBER`), brak wniosku o ponowne rozpatrzenie (apelacja jest tylko w spinkach: `thread_social_models.py:54`) | `ClinicDiscussion.tsx:24`; `clinic_moderation.py:55-65`; `clinic_discussion.py:157-161` | M |
| W2 | Konta: komentowanie wymaga zalogowania i potwierdzonego e-maila (`require_verified`, `clinic_discussion.py:76,89,141`), brak logowania przez Apple/Google (wymóg sklepów: Sign in with Apple i usuwanie konta w aplikacji, zob. pamięć projektu o sklepach), brak ochrony przed botami poza limitami (CAPTCHA/Turnstile nie znaleziono w kodzie komentarzy) | `AccountDialog.tsx:45-52`; `accounts.py:48-57` (limit IP 20/h i nazwy 10/h) | M |
| W3 | Ustawienia powiadomień: temat „spinki” i `push_thread_replies` do usunięcia; brakuje ustawień per osoba (tryb, częstotliwość, godziny ciszy), podglądu ostatnich powiadomień w aplikacji (jest dzwonek w SocialNavigation, który zniknie z paskiem) | `AccountPhase2.tsx:106-147`; `notification_models.py:31-39` | M |
| W4 | Push działa na poziomie tematów i obserwowanych; brak: kolejki priorytetów, retry z wykładniczym opóźnieniem (jedna próba, 404/410 usuwa subskrypcję, inne błędy tylko log: `push.py:30-37`), ttl 3600 s, brak metryk dostarczenia, brak kosztów SMS/aplikacji; iOS wymaga PWA dodanej do ekranu głównego (banner jest) | `push.py`; `PwaControls.tsx:34-48` | M |
| W5 | PWA: jest manifest, ikony 192/512 i maskable (200 na produkcji), offline.html, service worker (cache `spin-pwa-v1`, tylko `/api/clinic/stats` i `/spins`, 3 s timeout, 5 min ważności), instalacja Android i instrukcja iOS. Braki: brak cache stron Kliniki offline (nawigacja → tylko offline.html), brak `screenshots` i `shortcuts` zgodnych z nowymi działami (skrót „Spinki”), brak wersjonowania SW poza stałą v1, brak badge/odznaki, brak testu Lighthouse PWA w repo | `sw.js:2,42-55`; `manifest.ts:13-27` | S-M |
| W6 | Oferta i raporty: strona /dla-redakcji ma formularz, próbkę raportu (`/api/raporty/probka/` zwraca `{"available":false}` na produkcji, więc sekcja próbki jest pusta) i przykład spinki do usunięcia; ceny nie są publiczne (zgodnie z decyzją), brak strony aplikacji/alertów jako produktu | `InstitutionReports.tsx:41`; live GET | M |
| W7 | Brak ścieżki „co dalej” po usunięciu: stare linki do /spinki/{id} z powiadomień e-mail, udostępnień na X i kart (`card.png`, `thread_card`) | `next.config.js:19-26`; `urls.py:89` | S |
| W8 | Strażnicy i raporty: planowy raport dnia, alarmy centrum i puls serwera liczą kamienie milowe spinek (A5); bez usunięcia będą fałszywe alarmy | `daily_schedule.py:294-312`, `duty_extra.py:96-135` | S |

### Miłe

| # | Luka | Dowód | Praca |
|---|---|---|---|
| M1 | Dane strukturalne (JSON-LD) nie występują w ogóle (grep: brak `ld+json`); diagnozy mają OG i kartę PNG, sitemapa zawiera diagnozy | `klinika/[id]/page.tsx:7-30`; `sitemap.ts:7-47` | S |
| M2 | Sitemapa: brak /klinika/przekazy, /klinika/wywiady, /klinika/diagnozy, wywiadów i przekazów dnia jako URL-i; ostatnia modyfikacja stała dla części stron | `sitemap.ts:12-30` | S |
| M3 | Sitemapa i robots: /konto zablokowany (dobrze); brak noindex dla pustych list | `robots.ts:9` | S |
| M4 | Alerty e-mail codzienne: jest dla przeszłość.today (`przeszlosc_alerts.py`), dla spin.clinic jest „digest” kont (daily/weekly) oraz newsletter | `notification_tasks.py:140-186` | S |
| M5 | Strona /thread/[slug] (stary model) bez wyraźnego miejsca w nawigacji | `thread/[slug]/page.tsx` | S |

## C. Proponowana kolejność prac

0. Audyt (ten dokument), potem przegląd z Prawnikiem (K5) i decyzje z listy pytań.
1. Zamrożenie i archiwum: eksport danych spinek do plików (read-only), tag gałęzi `spinki-freeze`, kopia kodu `community/*` do osobnego pakietu. Bez zmian produktu.
2. Design nowej powłoki i głównej (pętla designu: przewodnik Projektanta, zrzuty 1440/390, panel UX/laik/dostępność, pomiar odstępów `gust/odstepy.js`): menu (Klinika, Przekazy, Wywiady, Raporty, Szukaj, Konto), główna z przekazami dnia, diagnozami i wywiadem dnia, wpis o aplikacji. Prawa: Jakob (konwencje menu), Hick (mniej wyborów), Peak-End.
3. Wycięcie w kolejności bezpiecznej: (a) odpiąć sygnały `signals.py:36-75` i zadania harmonogramu A5 oraz strażnika `duty_extra.py:96`; (b) flaga THREADS_ENABLED=false na produkcji i w teście; (c) usunąć trasy i komponenty (A1, A2); (d) przekierowania; (e) teksty prawne; (f) dopiero po zamrożeniu: migracje usuwające modele (osobny krok z zatwierdzeniem właściciela, jeden właściciel migracji).
4. Komentowanie: przekazy dnia (K4), liczniki i powiadomienia (W1), apelacja, moderacja ludzka, Prawnik (zgłaszanie, usuwanie, małoletni).
5. Alerty: najpierw decyzja o źródle i budżecie (K3), potem kolejka, retry, ustawienia per osoba, metryki dostarczenia (W3, W4).
6. PWA: dopracowanie (W5), test na Android i iOS, potem sklepy (konto Google Play, później Apple).
7. Raporty i oferta: próbka raportu, strona aplikacji i alertów (W6).

## D. Ryzyka

1. Dane: migracja usuwająca PersonalContextThread kaskadowo usunie tysiące powiązanych wierszy; ThreadModerationDecision (PROTECT) może zablokować kasowanie. Najpierw archiwum, migracje na kopii z rollbackiem.
2. Zapis diagnoz: sygnał `signals.py:36-39` wywołuje kod spinek przy każdym zapisie SpinDiagnosis; błąd tu zatrzyma publikację diagnoz (treść jest najwyższym priorytetem wg Dyrygenta).
3. Maile i kolejki: `thread-moderation-mail` działa co minutę; wiersze ThreadModerationMail w kolejce przestaną być wysyłane, a decyzje moderacji nie dojdą do autorów; Notification o URL `/spinki/*` zostaną martwymi linkami w e-mailach i push. Opróżnić kolejkę przed wyłączeniem.
4. SEO i linki zewnętrzne: /spinki/{id} i `card.png` mogą być już udostępnione na X i w sieci; sitemapa ich nie zawiera (dobrze), ale linki zewnętrzne trzeba przekierować, nie zwracać 404. Przekierowania w `next.config.js` dziś prowadzą do /spinki (nie ma łańcucha po usunięciu trasy: zmienić cel).
5. RODO: eksport i kasowanie konta (`account_lifecycle.py:240-329`) obejmują spinki; wycięcie bez archiwum zamknie prawo dostępu do danych, które nadal istnieją. Polityka prywatności musi mówić prawdę przed i po (A3).
6. Stan: flaga THREADS_ENABLED jest współdzielona z podglądem (cookie `sc_preview`, `features.ts:12-26`); wyłączenie jej na produkcji nie wyłącza podglądu zespołu, co może maskować błędy.
7. Push: zmiana tematów w `push.py:9` wymaga migracji subskrypcji; iOS PWA push działa tylko po instalacji.
8. X: koszty i warunki API, limity dzienne (`political_polling.py:48-50`); zwiększenie częstotliwości podniesie koszt. Brak wiedzy o aktualnym planie X.
9. Spójność wizualna: html[data-view] z SectionBar steruje kolorami tła (`SectionBar.tsx:32`); usunięcie widoku „tropy” zmieni tło głównej.
10. Dwa modele „wątków”: łatwo usunąć pochopnie news.Thread, który zasila `portal.py` i stronę /thread.

## E. Strona główna i zrzuty (https://spin.clinic odpowiada: HTTP 200)

Wykonano niewidocznym Playwrightem zrzuty `/`, `/klinika`, `/klinika/6288` w 1440 i 390 px (pliki w katalogu roboczym sesji: scratchpad `shots/`). Poniżej obserwacje z zrzutów i z DOM; nie uruchamiano narzędzia `odstepy.js` ani pomiaru położeń krawędzi (patrz F).

Strona główna (spinki, stan przed wycięciem):
- 1440: 3 wiersze w feedzie, pod nimi ok. 380 px czarnej pustki; zakładki „Czytelnicy” i „Izba przyjęć” prowadzą do pustych list (zero spinek od czytelników). Prawo: Hick (zbędne wybory), Goal-Gradient/Peak-End (słaby koniec strony).
- Wiersze mają dwie etykiety i liczniki (ikona „spinki” 5/3/4 i dymek 0): licznik 0 komentarzy w każdym wierszu; spinka jako ikona bez opisu (Jakob, Recognition over Recall).
- 390: dolny pasek 5 pozycji (Spinki, Klinika, Szukaj, Profil, Więcej), poziomy pasek zakładek ucina „Izba przyjęć” (wymaga przewijania), brak poziomego przewijania strony (scrollWidth = 390).
- Tytuł h1 ukryty (sr-only) „Diagnozy Dr. Spina i spinki”.

Klinika `/klinika` (zostaje, 1440; 5377 px wysokości, 390: 9755 px):
- Struktura jest logiczna: wskaźniki, Przekazy dnia (2 boksy równej wysokości rząd/opozycja), Najnowsze diagnozy, Wywiad dnia, Najwyższa siła spinu, newsletter. Na telefonie strona ma ok. 10 tys. px; warto skrócić (Hick, Chunking).
- Tabela i wykres po prawej stronie nagłówka: podpisy liczb i dat wykresu wymagają pomiaru wspólnych linii (zasada 3).
- Pasek „Powiadomimy Cię o starcie pełnej wersji” (newsletter) jest jedynym wezwaniem do działania, bez wzmianki o aplikacji.

Diagnoza `/klinika/6288` (zostaje):
- Pusta sekcja „W spinkach: Nie ma jeszcze publicznych spinek” (do usunięcia, ContextThreadStrip).
- Sekcja „Dyskusja” jest węższa i wycentrowana względem kolumny treści (zrzut: box dyskusji ok. x=195-573 w skali zrzutu przy kolumnie treści 345-650), co łamie zasadę wspólnych linii i marginesów (zasada 3). Pod nią „Kolejne diagnozy” w szerszym boksie. Prawo: Common Region, Similarity.
- Stan pusty dyskusji: „Nie ma jeszcze komentarzy. Rozpocznij dyskusję” oraz „Trafne + 0 Nietrafne − 0” bez zachęty innej niż logowanie (Von Restorff: jedno wyróżnienie, przycisk „Zaloguj się, aby ocenić i komentować” jest tylko linkiem).
- Tekst odnośnika „Zgłoś błąd” w nagłówku, a obok „Jak czytać wynik?”: dwa drobne odnośniki obok siebie (Fitts: cele poniżej 44 px; nie mierzono).

Dostępność i wydajność (tylko z kodu i odpowiedzi):
- Jest link „Przejdź do treści” (`layout.tsx`), `lang="pl"`, nawigacje z aria-label, strona bez poziomego przewijania w 390 px.
- Główna ładuje 28 KB HTML, Klinika 31 KB, diagnoza 29-31 KB; endpoint /api/clinic/ zwraca 415 KB JSON (używany przez sitemapę i listy): kandydat do paginacji lub okrojenia (niezmierzone w przeglądarce).
- Film wstępny 60 s w iframe na pierwszej wizycie (`FirstVisitIntro.tsx`) ma „Pomiń” i szanuje prefers-reduced-motion.

## F. Czego nie zweryfikowano

1. Liczby w produkcyjnej bazie (opinie, ulubione, komentarze, obserwowania wątków, subskrypcje push, zgłoszenia, kolejka maili): brak dostępu; podano tylko liczby z publicznego API (3 publiczne spinki, id do 98).
2. Czy na produkcji ACCOUNTS_ENABLED i PUSH_ENABLED są faktycznie włączone dla użytkowników: widziano „Zaloguj się” w nawigacji i `enabled:true` z /api/push/subscriptions/; nie testowano rejestracji, logowania, wysyłki push ani komentarza (zapisy zabronione).
3. Czy flaga NEXT_PUBLIC_THREADS_ENABLED jest ustawiona przez zmienną środowiska serwera: wywnioskowano z zachowania strony, nie odczytano konfiguracji (nie czytano .env).
4. Rzeczywiste opóźnienie alertów (X API, plan, koszt), stan flagi X_POLITICAL_POLLING_ENABLED i limitów: nie sprawdzano.
5. Pomiary położeń i odstępów (`node C:\Users\User\zbudujmi\gust\odstepy.js`), panel designu (recenzenci), Lighthouse, kontrast, nawigacja klawiaturą, czytnik ekranu: nie wykonano; oceny layoutu pochodzą z oglądu zrzutów.
6. Testy backend i frontend nie były uruchamiane (audyt tylko do odczytu); nie wiadomo, które testy padną po wycięciu poza wynikiem wyszukiwania tekstu.
7. Zrzuty 390 px Kliniki i diagnozy zostały zrobione, ale oglądnięto tylko 1440 dla Kliniki i diagnozy oraz 390 dla głównej; metryki 390 dla pozostałych pochodzą z DOM.
8. Czy HomeDrSpin.tsx jest jeszcze montowany (HomePage importuje HomeThreads, nie HomeDrSpin); nie prześledzono każdego importu w `packages/ui/src/index.ts`.
9. Użycie `frontend-przeszlosc` i wspólnego pakietu ui przez przeszłość.today po usunięciu komponentów spinek (przeszłość.today to ta sama aplikacja frontend-spin według `FirstVisitIntro.tsx`, więc usunięcie komponentów może wpłynąć też na nią).
10. Treść prawna w wersji EN i w dokumentach `frontend-spin/lib/documents` pod kątem spinek: tylko liczba trafień.
11. Katalog `.claude/worktrees/agent-aae28f7654b41f485` zawiera kopię repo (wyłączono z audytu; nie analizowano).
12. Dosłowny napis „Wiadomości · Klinika · Nitki” nie występuje w repo (patrz A3).

## G. Dziesięć pytań do właściciela

1. Czy wycinamy spinki w jednym kroku (flaga false + usunięcie tras) czy dwuetapowo: najpierw ukrycie (flaga false, kod zostaje), po eksporcie dopiero migracje usuwające tabele?
2. Czy spinki Dr. Spina (automatyczne spinki z diagnoz i przekazów dnia) mają zniknąć razem z czytelniczymi, skoro to one dziś tworzą główną? Co ma być nową główną: lista diagnoz i przekazów dnia czy strona Klinika?
3. Czy mogę dostać zgodę na wykonanie na serwerze samych zapytań COUNT (liczba spinek, opinii, ulubionych, komentarzy, obserwowań, subskrypcji push, kolejka ThreadModerationMail), żeby uzupełnić dane do archiwum?
4. Alerty „błyskawiczne”: jaki cel opóźnienia (sekundy, minuty), jaki miesięczny budżet na źródło X (dziś domyślnie 5 USD i 100 żądań dziennie) i czy dopuszczamy inne źródła (RSS stron partii, YouTube, oficjalne strony)?
5. Czy alerty mają nocą budzić (dziś cisza 23:00-07:00) i czy to ma być ustawienie użytkownika?
6. Co z starym modelem `news.Thread` i stroną /thread/[slug] (ulubione, oceny, edycje redakcyjne government/opposition w `portal.py`): usuwamy, ukrywamy czy zachowujemy dla oferty dla redakcji?
7. Sygnały lobbingu i nowe narracje (`signal_threads.py`, wątki wykrywane bez AI): przenieść do raportów B2B zamiast kasować?
8. Komentowanie: czy komentarze pod diagnozami, przekazami dnia i wywiadach mają wymagać potwierdzonego e-maila (jak dziś), czy dopuszczamy logowanie przez Apple i Google, i czy włączyć publicznie liczniki trafne/nietrafne (stała SHOW_DISCUSSION_COUNTS)?
9. Kto moderuje komentarze (człowiek czy tylko filtr AI na darmowym Groq) i jaki jest dopuszczalny czas reakcji na zgłoszenie (potrzebne do regulaminu usługi hostingowej)?
10. Czy aplikacja ma mieć osobną nazwę i konto, czy zostaje pod marką spin.clinic, i czy startujemy PWA bez sklepów do czasu ustalonej liczby użytkowników (zakres sklepów wymaga osobnej zgody wg PLAN_AKTUALNY.md, pkt APP-01)?
