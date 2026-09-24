# Lokalna koordynacja Codex–Claude Code

Koordynacja korzysta z plikowej kolejki w `.local/ai-coordination/claude`. Katalog `.local` pozostaje poza Git i nie może zawierać sekretów.

1. Codex lub właściciel zapisuje samowystarczalne zadanie Markdown w `claude/inbox`, z rosnącym numerem na początku nazwy.
2. `Run-Claude-Queue.ps1` przenosi jedno zadanie do `running`, uruchamia Claude Code w trybie nieinteraktywnym i zapisuje wynik do `logs`.
3. Sukces przenosi zadanie do `done`, błąd do `failed`.
4. Claude pracuje wyłącznie we własnym worktree i tworzy lokalny commit bez pushowania.
5. Codex czyta wynik, przegląda diff i dopiero potem integruje wybrany commit.

Kolejka nie daje Claude dostępu do produkcyjnych sekretów ani Supabase. Dozwolone narzędzia są ograniczone do plików, oficjalnego researchu, testów i lokalnego Git. Proces kończy się po maksymalnie 10 godzinach albo po utworzeniu pliku `STOP_CLAUDE_QUEUE`.
