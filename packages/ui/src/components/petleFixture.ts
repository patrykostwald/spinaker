// Przykładowe dane widoku „Pętle” (podgląd lokalny i zrzuty); kształt zgodny z GET /api/staff/petle/.
export type LoopState = 'ok' | 'warn' | 'bad' | 'idle';
export type CategoryKey = 'tresc' | 'agenci' | 'przeszlosc' | 'niezawodnosc' | 'konsylium' | 'dane';
export type Loop = { key: string; label: string; state: LoopState; reason: string; last_run: string | null;
  outputs_24h: number; outputs_7d: number; pending: number; consumer: string; cadence_h: number };
export type LoopCategory = { key: CategoryKey; label: string; loops: Loop[] };
export type LoopsSnapshot = { generated_at: string; summary: Record<LoopState, number>; categories: LoopCategory[] };

const ago = (h: number) => new Date(Date.now() - h * 3600000).toISOString();
const loop = (key: string, label: string, state: LoopState, reason: string, lastH: number | null, d: number, w: number, pending: number, consumer: string, cadence_h: number): Loop =>
  ({ key, label, state, reason, last_run: lastH === null ? null : ago(lastH), outputs_24h: d, outputs_7d: w, pending, consumer, cadence_h });

const categories: LoopCategory[] = [
  { key: 'tresc', label: 'Treść serwisu', loops: [
    loop('dr-spin', 'Dr Spin - diagnozy', 'ok', 'Diagnozy powstają w rytmie, kolejka mała.', 0.4, 46, 301, 3, 'Klinika i strona główna', 1),
    loop('wywiady', 'Wywiady dnia', 'ok', 'Dwa wywiady z wczoraj zdiagnozowane.', 6, 2, 13, 0, 'Klinika - wywiady', 24),
    loop('spinki', 'Spinki i nitki', 'warn', 'Mniej połączeń niż zwykle: 4 zamiast ~12 dziennie.', 9, 4, 61, 7, 'Spinki', 6),
    loop('tygodnik', 'Raport tygodnia', 'idle', 'Czeka na niedzielę - następny bieg 12.10.', 98, 0, 1, 0, 'Newsletter i raporty', 168),
    loop('jezyk', 'Prosty język', 'ok', 'Teksty przepisane i sprawdzone.', 1.2, 38, 240, 1, 'Wszystkie boksy', 2),
  ] },
  { key: 'agenci', label: 'Agenci', loops: [
    loop('strateg', 'Strateg', 'ok', 'Trzy pomysły w tym tygodniu.', 20, 1, 6, 2, 'Panel - decyzje właściciela', 24),
    loop('pielgrzym', 'Pielgrzym', 'ok', 'Propozycje dla Konsylium zebrane.', 22, 1, 7, 0, 'Konsylium', 24),
    loop('projektant', 'Projektant UX/UI', 'warn', 'Raport bez zrzutów 390 px - przeglądarka nie wstała.', 30, 0, 3, 1, 'Front i zbudujmi', 24),
    loop('recenzent', 'Recenzent tekstów', 'ok', 'Teksty z dziś przejrzane.', 2, 18, 120, 0, 'Publikacja', 4),
    loop('seba', 'Seba', 'bad', 'Brak darmowego okna od 3 dni - 9 pomysłów czeka na ocenę.', 74, 0, 2, 9, 'Strateg i Pielgrzym', 24),
    loop('pomysly', 'Pomysły do budowy', 'warn', 'Przyjęte pomysły nie mają zleceń budowy.', 26, 0, 4, 5, 'Codex i Claude', 24),
  ] },
  { key: 'przeszlosc', label: 'przeszłość.today', loops: [
    loop('osint', 'Pracownia OSINT', 'ok', 'Nowe tematy i powiązania w bazie.', 3, 27, 180, 4, 'przeszłość.today', 6),
    loop('tematy', 'Drzewo tematów', 'ok', 'Drzewo odświeżone.', 5, 6, 41, 0, 'Strona główna przeszłości', 12),
    loop('archiwa', 'Archiwa i rejestry', 'bad', 'KRS odpowiada 503 od 26 h - zbieranie stoi.', 26, 0, 88, 14, 'Pracownia OSINT', 6),
  ] },
  { key: 'niezawodnosc', label: 'Niezawodność', loops: [
    loop('dyrygent', 'Dyrygent', 'ok', 'Limity rozdzielone według hierarchii.', 0.2, 96, 670, 0, 'Wszystkie pętle', 0.25),
    loop('automatyk', 'Automatyk', 'ok', 'Harmonogramy zgodne.', 0.9, 24, 168, 0, 'Panel dowodzenia', 1),
    loop('opiekunowie', 'Opiekunowie pętli', 'ok', 'Wszyscy opiekunowie zgłosili się.', 1, 12, 84, 0, 'Dyrygent', 2),
    loop('mechanik', 'Mechanik', 'idle', 'Nic do naprawy.', 50, 0, 2, 0, 'Serwer', 24),
  ] },
  { key: 'konsylium', label: 'Konsylium', loops: [
    loop('rada', 'Rada modeli', 'ok', 'Głosowania z dziś zamknięte.', 4, 9, 58, 0, 'Konsylium i diagnozy', 6),
    loop('rekruter', 'Rekruter', 'warn', 'Gemma odrzuca zapytania (429) - ponowienie o 2:15.', 28, 0, 3, 1, 'Rada modeli', 24),
    loop('karta', 'Karta Konsylium', 'idle', 'Bez zmian w karcie.', 140, 0, 0, 0, 'O nas - karta', 168),
  ] },
  { key: 'dane', label: 'Dane i zbieracze', loops: [
    loop('rss', 'Kanały RSS', 'warn', '60 z 75 źródeł czeka na zgodę instrukcji.', 0.5, 210, 1600, 60, 'Dr Spin', 0.5),
    loop('x', 'Wpisy z X', 'ok', 'Zbieranie wróciło po poprawce since_id.', 0.3, 340, 1900, 0, 'Dr Spin i Spinki', 0.5),
    loop('sejm', 'API Sejmu', 'ok', 'Posiedzenia i głosowania pobrane.', 2, 55, 400, 0, 'Spinki i wskaźniki', 3),
    loop('imap', 'Poczta IMAP', 'ok', 'Komunikaty partii odebrane.', 0.7, 14, 92, 0, 'Dr Spin', 1),
    loop('youtube', 'YouTube', 'bad', 'Limit klucza wyczerpany - pobieranie wstrzymane do 9:00.', 15, 0, 120, 22, 'Wywiady dnia', 6),
    loop('kprm', 'KPRM gov.pl', 'idle', 'Kanał wyłączony - źródło przestało działać.', null, 0, 0, 0, 'Dr Spin', 24),
  ] },
];
const count = (s: LoopState) => categories.reduce((n, c) => n + c.loops.filter(l => l.state === s).length, 0);

export const PETLE_FIXTURE: LoopsSnapshot = {
  generated_at: new Date().toISOString(),
  summary: { ok: count('ok'), warn: count('warn'), bad: count('bad'), idle: count('idle') },
  categories,
};
