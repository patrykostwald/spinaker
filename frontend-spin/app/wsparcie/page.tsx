import Link from 'next/link';
import { Button, InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterSignup } from '@spin-clinic/ui';

export const metadata = { title: 'Wsparcie · spin.clinic' };
// Linki BUYCOFFEE_URL i PATRONITE_URL czytamy z .env.production przy każdym wejściu, nie przy budowaniu obrazu.
export const dynamic = 'force-dynamic';

function publicSupportUrl(value: string | undefined) {
  try {
    const url = new URL(value || '');
    return url.protocol === 'https:' ? url.toString() : '';
  } catch {
    return '';
  }
}

/** Koszty z konfiguracji (twardy budżet AI) i rodzaje opłat — bez kwot, których nie znamy z faktur. */
const COSTS: Array<[string, string]> = [
  ['Diagnozy Dr. Spina', 'konsylium działa na darmowych modelach; płacimy za sprawdzanie faktów w wyszukiwarce Google (Gemini), za docisk Claude przy spornych i mocnych spinach oraz za ocenę wywiadu dnia.'],
  ['Posty polityków', 'oficjalne, płatne API X — płacimy za każde pobranie.'],
  ['Wywiad dnia', 'transkrypcja nagrania (Gemini) — płatna za zużycie, drobne kwoty dziennie.'],
  ['Strażnik, przekazy dnia, filmy', '0 zł — robimy je na darmowych limitach (Groq, NVIDIA NIM, YouTube) i wykorzystujemy je do końca każdego dnia.'],
  ['Serwer, baza, kopie zapasowe, domena', 'stały koszt miesięczny.'],
];

/** Jawny cel miesięczny i zebrana kwota — ustawiane w .env.production (SUPPORT_MONTHLY_GOAL_PLN, SUPPORT_MONTHLY_RAISED_PLN). */
function supportProgress() {
  const goal = Number(process.env.SUPPORT_MONTHLY_GOAL_PLN || 0);
  const raised = Math.max(0, Number(process.env.SUPPORT_MONTHLY_RAISED_PLN || 0));
  if (!Number.isFinite(goal) || goal <= 0) return null;
  return { goal, raised, percent: Math.min(100, Math.round((raised / goal) * 100)) };
}

const GOALS: Array<[string, string]> = [
  ['Utrzymanie', 'Pełny miesiąc Kliniki: diagnozy, API X i serwer. Gdy wpłat jest mniej, zmniejszamy dzienną liczbę diagnoz; gdy więcej — sprawdzamy więcej wypowiedzi.'],
  ['Faza II', 'Konta czytelników, nitki kontekstowe z materiałów z Bazy i strażnica zmian, która pokaże, gdy źródło po publikacji zmieni albo usunie materiał.'],
  ['Własny serwer AI', 'Maszyna z kartą graficzną i otwarte modele, także polskie. Koszt jednej diagnozy spadnie prawie do zera, a Klinika uniezależni się od cen i regulaminów wielkich firm.'],
];

export default function SupportPage() {
  const buycoffee = publicSupportUrl(process.env.BUYCOFFEE_URL);
  const patronite = publicSupportUrl(process.env.PATRONITE_URL);
  const progress = supportProgress();
  const links = [
    buycoffee && { label: 'Postaw kawę na BuyCoffee', href: buycoffee },
    patronite && { label: 'Wspieraj co miesiąc na Patronite', href: patronite },
  ].filter(Boolean) as { label: string; href: string }[];

  return <InfoPage eyebrow="WSPARCIE" title="Politycy mają spin doktorów. My mamy spin.clinic." lead="spin.clinic to niezależny projekt, który pokazuje wiadomości ze źródłami i rozkłada przekazy polityków na czynniki pierwsze. Utrzymują go wyłącznie czytelnicy — bez reklam, sponsorów i partyjnych pieniędzy.">
    <section><h2>Kto za tym stoi</h2><p>Projekt buduje jedna osoba, która nie jest i nigdy nie była członkiem żadnej partii politycznej, redakcji ani organizacji politycznej. Nie reprezentuje żadnego obozu. Cały serwis powstaje przy wsparciu narzędzi sztucznej inteligencji — od kodu po analizę przekazów — i jest odpowiedzią na prostą nierówność: politycy mają zespoły od wizerunku, a obywatele zwykle nie mają nikogo. Operatorem serwisu jest iapply sp. z o.o. z Poznania.</p></section>
    <section><h2>Na co idą pieniądze</h2>
      <dl className="sc-support-costs">{COSTS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
      <p className="sc-support-note">Dziś pokrywamy te koszty sami. Jedna kawa za 10 zł to kilka kolejnych diagnoz albo kilka dni pracy strażnika z serwerem.</p>
    </section>
    {progress ? <section aria-labelledby="support-goal-title"><h2 id="support-goal-title">Cel na ten miesiąc</h2>
      <div className="sc-support-goal" role="img" aria-label={`Zebrano ${progress.raised} z ${progress.goal} zł (${progress.percent}%)`}>
        <div className="sc-support-goal__bar"><span style={{ width: `${progress.percent}%` }} /></div>
        <p><strong>{progress.raised.toLocaleString('pl-PL')} zł</strong> z {progress.goal.toLocaleString('pl-PL')} zł · {progress.percent}%</p>
      </div>
      <p className="sc-support-note">Cel pokrywa pełny miesiąc: diagnozy Dr. Spina, API X, transkrypcje i serwer. Kwotę aktualizujemy ręcznie po wpłatach.</p>
    </section> : null}
    <section><h2>Na co zbieramy</h2>
      <dl className="sc-support-costs">{GOALS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
      <p className="sc-support-note">Co dokładnie jest w każdej fazie, opisujemy w <Link href="/o-nas#fazy">O nas → Trzy fazy projektu</Link>.</p>
    </section>
    <section><h2>Wsparcie nie kupuje wpływu</h2><p>Żadna wpłata nie daje wpływu na diagnozy, na wybór czytanych kont ani na treść serwisu. Dr. Spin ocenia rządzących i opozycję według tych samych zasad, a jego diagnoz nikt nie poprawia. Nie przyjmujemy wpłat od partii, polityków ani ich fundacji.</p></section>
    <section><h2>Wybierz sposób wsparcia</h2>{links.length ? <><p>Jednorazowo — BuyCoffee, co miesiąc — Patronite. Wpłaty obsługują te serwisy; spin.clinic nie przetwarza danych płatniczych.</p><div className="sc-info-page__actions">{links.map(link => <Button key={link.href} href={link.href} variant="primary">{link.label}</Button>)}</div></> : <p>Linki do BuyCoffee i Patronite pojawią się tutaj wkrótce. Nie pobieramy płatności bezpośrednio w serwisie.</p>}</section>
    <section><h2>Dziękujemy</h2><p>Jeśli nie możesz wesprzeć finansowo, udostępnij diagnozę z <Link href="/klinika">Kliniki</Link> na X — to też bardzo pomaga.</p></section>
    <NewsletterSignup source="wsparcie" />
  </InfoPage>;
}
