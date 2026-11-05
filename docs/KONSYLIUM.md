# Konsylium AI spin.clinic — skład, narzędzia i plan rozbudowy (research 29.09.2026)

Cel: każdy wpis polityka zbadany możliwie wieloma **darmowymi** narzędziami różnych dostawców; płatne dopiero powyżej progu
(silny spin lub brak zgody konsylium). Zasady działania — w `docs/KARTA_KONSYLIUM.md`.

## 1. Stan dziś (kod: `backend/news/clinic_council.py`, `clinic_ai.py`)

| Rola | Model / narzędzie | Dostawca | Koszt |
|---|---|---|---|
| Strażnik (izba przyjęć) | darmowe modele | Groq / NVIDIA | 0 |
| Członkowie konsylium | GPT-oss 20B, Qwen 27B | Groq | 0 |
| | Nemotron 120B | NVIDIA NIM | 0 |
| | Gemini Flash | Google | 0 (limit dzienny) |
| Przewodniczący (uzasadnienie) | Gemini Flash | Google | 0 |
| Językoznawca | Qwen 27B | Groq | 0 |
| Recenzent (zgodność z zasadami) | Nemotron 120B | NVIDIA NIM | 0 |
| Sprawdzanie faktów | Gemini + wyszukiwarka Google | Google | 0 (limit) |
| Eskalacja (spór < 2/3 albo siła ≥ 70) | Claude + wyszukiwanie w sieci | Anthropic | płatne, w budżecie dziennym |
| Słowa nacechowane | słownik PL + wskazania konsylium | własny | 0 |
| Rodziny technik | słownik 21 kategorii | własny | 0 |

## 2. Co dodać — wyniki researchu

### A. „Badania laboratoryjne” — narzędzia, które nie są czatem (inne spojrzenie na ten sam wpis)

| Narzędzie | Co mierzy | Język | Koszt / wymagania | Decyzja |
|---|---|---|---|---|
| Detektor technik perswazji XLM-RoBERTa (zwycięzca SemEval-2023 Task 3, 1. miejsce m.in. dla polskiego; KInIT) | 23 techniki perswazji w tekście | wielojęzyczny, PL | kod publiczny; wagi trzeba wytrenować (GPU) | **faza III** (własna maszyna) — niezależny „drugi instrument” do technik |
| HerBERT — wydźwięk (`Voicelab/herbert-base-cased-sentiment`) | negatywny / neutralny / pozytywny | PL | darmowy, działa na CPU serwera | **tak — od razu** |
| HerBERT — mowa nienawiści (`dkleczek/Polish-Hate-Speech-Detection-Herbert-Large`, zbiór BAN-PL) | treści obraźliwe | PL | darmowy, CPU (wolniej, kilka wpisów dziennie — OK) | **tak** |
| Perspective API (Google) | toksyczność | PL | wyłączane 31.12.2026 | **nie** |

### B. Członkowie konsylium — więcej firm, w tym polskie modele

| Model | Dostawca | Darmowy limit | Uwagi | Decyzja |
|---|---|---|---|---|
| **PLLuM** (polski, rządowy) | API PLLuM | 1000 zapytań/dzień, 60/min | natywna polszczyzna | **tak — językoznawca i członek** |
| **Bielik** (polski, Apache 2.0) | Cyfronet LLM Lab, PCSS AI HUB, CloudFerro Sherlock, Hugging Face | zależnie od dostawcy | natywna polszczyzna | **tak — członek** |
| **Mistral** (Francja) | Mistral „Experiment” | ~1 mld tokenów/mies., ~1 zapytanie/s | domyślnie trenuje na danych — **wyłączyć w Admin Console → Privacy** | **tak, po wyłączeniu trenowania** |
| Llama / Gemma / Qwen / DeepSeek (destylaty) | Cloudflare Workers AI | 10 000 „neuronów”/dzień (~1300 odpowiedzi) | jedno konto, wiele modeli | **tak — zapas i dodatkowy głos** |
| różne darmowe modele | OpenRouter | ~50 zapytań/dzień | jeden klucz, wiele modeli | **tak — awaryjnie** |
| SambaNova | SambaNova Cloud | ~20 zapytań/dzień, od 08.2026 wymaga karty | | nie |
| Cerebras | — | darmowy dostęp zmieniony na płatny test | | nie |
| GitHub Models | — | zamknięte 30.07.2026 | | nie |

**Zasada składu:** każdą diagnozę stawia co najmniej 4 członków od **co najmniej 3 różnych firm**, w tym **co najmniej 1 model polski**.

### C. Dowody i sprawdzanie faktów

| Narzędzie | Co daje | Koszt | Decyzja |
|---|---|---|---|
| **Google Fact Check Tools API** (ClaimReview) | czy twierdzenie było już sprawdzane (Demagog, OKO.press, AFP Sprawdzam i inne) | darmowe, klucz API | **tak** |
| **GUS — API BDL** | dane statystyczne do twierdzeń z liczbami | darmowe; z kluczem 5× wyższy limit | **tak** |
| Eurostat, NBP (kursy, stopy), API Sejmu, ELI/ISAP, KRS | dane urzędowe | darmowe (część już używamy) | **tak — dopiąć brakujące** |
| **Wayback Machine — Save Page Now** | trwała kopia wpisu i źródeł (dowód, gdy autor usunie) | darmowe konto archive.org, ~6 zapisów/min | **tak** |
| Firecrawl | pobranie treści źródła do sprawdzenia | 1000 kredytów/mies. | **tak — pobieranie źródeł** |
| Google Programmable Search | wyszukiwanie | zamknięte dla nowych klientów | nie |
| Brave Search API | wyszukiwanie | darmowy plan usunięty | nie |
| Exa / Tavily | wyszukiwanie dla AI | płatne (~7–17 USD / 1000) | **opcjonalnie powyżej progu** |

### D. Płatne powyżej progu

- **Claude** (Anthropic) z wyszukiwaniem — już jest; zostaje jako eskalacja (spór konsylium < 2/3, siła ≥ 70, twierdzenie niesprawdzone przez darmowe narzędzia).
- Do rozważenia: **Exa** jako płatna wyszukiwarka dowodów przy eskalacji (tańsza niż druga płatna diagnoza).

## 3. Proces diagnozy po rozbudowie

1. **Strażnik** wybiera wpis wart zbadania (bez zmian).
2. **Badania laboratoryjne** (równolegle, darmowo): słownik słów nacechowanych, HerBERT-wydźwięk, HerBERT-mowa nienawiści,
   kopia w Wayback Machine, zapytanie do Fact Check Tools o każde twierdzenie.
3. **Konsylium** (4–6 członków z ≥ 3 firm, ≥ 1 polski): każdy niezależnie — werdykt, siła, techniki (kategoria z listy), twierdzenia, słowa nacechowane.
4. **Dowody:** Gemini + wyszukiwarka, dane urzędowe (GUS, Eurostat, NBP, Sejm, ELI), znalezione fact-checki.
5. **Przewodniczący** pisze uzasadnienie; **językoznawca** (PLLuM/Bielik) poprawia polszczyznę; **recenzent** sprawdza zgodność z Kartą.
6. **Eskalacja płatna** tylko przy sporze, sile ≥ 70 albo braku dowodów.
7. **Publikacja** automatyczna; na karcie: kto głosował, zgodność, rozrzut ocen, wyniki badań laboratoryjnych, zakres analizy.

## 4. Klucze do zdobycia (właściciel)

| Zmienna w `.env.production` | Skąd |
|---|---|
| `PLLUM_API_KEY` | portal API PLLuM |
| `BIELIK_API_KEY`, `BIELIK_API_URL` | wybrany dostawca Bielika (np. CloudFerro Sherlock / Cyfronet) |
| `MISTRAL_API_KEY` | console.mistral.ai (+ wyłączyć trenowanie w Privacy) |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_AI_TOKEN` | dash.cloudflare.com → Workers AI |
| `OPENROUTER_API_KEY` | openrouter.ai/keys |
| `INCEPTION_API_KEY` (+ `INCEPTION_NO_TRAINING=true` po wyłączeniu „Improve the model for everyone”) | platform.inceptionlabs.ai - Mercury 2.5, darmowa pula 100 mln tokenów; zadania poboczne (strażnik, odbiór spinu, agenci), do Konsylium tylko przez Rekrutera; stop przy 90% puli (`news/inception.py`) |
| `HF_TOKEN` | huggingface.co/settings/tokens (pobieranie modeli HerBERT) |
| `FACTCHECK_API_KEY` | Google Cloud → Fact Check Tools API (może być ten sam projekt co YouTube/Gemini) |
| `GUS_BDL_KEY` | api.stat.gov.pl (rejestracja) |
| `IA_S3_ACCESS`, `IA_S3_SECRET` | archive.org → konto → klucze S3 |
| `FIRECRAWL_API_KEY` | firecrawl.dev → API keys |

## Źródła

- SemEval-2023 Task 3, KInITVeraAI: https://arxiv.org/abs/2304.11924 · kod: https://github.com/kinit-sk/semeval2023-task3-persuasion-techniques
- HerBERT sentiment: https://huggingface.co/Voicelab/herbert-base-cased-sentiment · mowa nienawiści: https://huggingface.co/dkleczek/Polish-Hate-Speech-Detection-Herbert-Large · BAN-PL: https://arxiv.org/abs/2308.10592
- Perspective API — wyłączenie: https://www.lassomoderation.com/blog/what-is-perspective-api/
- PLLuM API: https://ainarzedziapolska.lovable.app/blog/pllum-api-poradnik-2026 · Bielik: https://bielik.ai/jak-korzystac-z-bielika/
- Inception: regulamin (trenowanie na danych, opt-out): https://www.inceptionlabs.ai/docs/terms-of-use · modele i ceny: https://docs.inceptionlabs.ai/get-started/models
- Mistral Experiment i trenowanie: https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training
- Cloudflare Workers AI: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Darmowe API LLM 2026: https://openrouter.ai/blog/tutorials/free-llm-apis-compared/ · SambaNova: https://docs.sambanova.ai/docs/en/models/rate-limits · GitHub Models: https://github.blog/changelog/2025-06-24-github-models-now-supports-moving-beyond-free-limits/
- Google Fact Check Tools API: https://developers.google.com/fact-check/tools/api · Demagog: https://demagog.org.pl/
- GUS BDL API: https://api.stat.gov.pl/Home/BdlApi
- Wayback Machine API: https://archive.org/help/wayback_api.php
- Wyszukiwarki dla AI 2026: https://www.firecrawl.dev/blog/best-web-search-apis · Google CSE: https://developers.google.com/custom-search/v1/overview
