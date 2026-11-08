import Link from 'next/link';
import { Button, InfoPage } from '@spin-clinic/ui/kit';
import { NewsletterSignup, SUPPORT_LINKS, glueShortWords } from '@spin-clinic/ui';

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

/** Koszty z konfiguracji (twardy budżet AI) i rodzaje opłat - bez kwot, których nie znamy z faktur. */
const COSTS: Array<[string, string]> = [
  ['Wpisy polityków', 'dostęp do wpisów na X przez oficjalne API.'],
  ['Analizy AI', 'płatne etapy analizy i sprawdzanie twierdzeń w źródłach.'],
  ['Nagrania', 'transkrypcje wywiadów.'],
  ['Utrzymanie', 'serwer, baza danych i kopie zapasowe.'],
];

/** Jawny cel miesięczny i zebrana kwota - ustawiane w .env.production (SUPPORT_MONTHLY_GOAL_PLN, SUPPORT_MONTHLY_RAISED_PLN). */
function supportProgress() {
  const rawGoal = process.env.SUPPORT_MONTHLY_GOAL_PLN;
  const rawRaised = process.env.SUPPORT_MONTHLY_RAISED_PLN;
  const updated = process.env.SUPPORT_UPDATED_AT;
  const goal = Number(rawGoal);
  const raised = Number(rawRaised);
  if (!rawGoal?.trim() || !Number.isFinite(goal) || goal <= 0) return null;
  const knownRaised = Boolean(rawRaised?.trim()) && Number.isFinite(raised) && raised >= 0;
  const timestamp = updated ? Date.parse(updated) : NaN;
  return { goal, raised: knownRaised ? raised : null, percent: knownRaised ? Math.min(100, Math.round(raised / goal * 100)) : null,
    updated: Number.isFinite(timestamp) ? new Date(timestamp).toLocaleDateString('pl-PL', { timeZone: 'Europe/Warsaw' }) : null };
}

/** Zobowiązanie: SUPPORT_PLEDGE_V2=true włącza nowy tekst dopiero po akceptacji właściciela (plan finansowy 6.10, ruch 6). */
const PLEDGE_V1 = 'Nie przyjmujemy darowizn od partii, polityków ani ich fundacji. Wpłata nie daje wpływu na wybór analizowanych materiałów ani wynik diagnozy. Dane i raporty sprzedajemy każdemu na tych samych warunkach; klient też nie ma wpływu na diagnozy. Zgłoszenia błędów rozpatrujemy według tych samych zasad, niezależnie od tego, kto je przesyła.';
const PLEDGE_V2 = 'Nie przyjmujemy darowizn od partii, polityków ani ich fundacji. Wpłata nie daje wpływu na wybór analizowanych materiałów ani wynik diagnozy. Dane i raporty sprzedajemy wszystkim na tych samych warunkach, także partiom i sztabom; kupujący nie mają wpływu na kryteria Dr. Spina, wybór wpisów, diagnozy ani treść serwisu. Ceny podajemy w ofercie, ta sama oferta dla każdego. Zgłoszenia błędów rozpatrujemy według tych samych zasad, niezależnie od tego, kto je przesyła.';

const GOALS: Array<[string, string]> = [
  ['Miesiąc pracy Kliniki', 'Diagnozy, API X i serwer. Gdy wpłat jest mniej, zmniejszamy dzienną liczbę diagnoz; gdy więcej - sprawdzamy więcej wypowiedzi.'],
  ['Strażnica zmian', 'Pokaże, gdy polityk albo redakcja po publikacji zmieni lub usunie wpis.'],
  ['Własny serwer AI', 'Maszyna z kartą graficzną i otwarte modele, także polskie. Celem jest lepsza kontrola kosztów i sposobu prowadzenia analiz.'],
];

export default function SupportPage() {
  const buycoffee = publicSupportUrl(process.env.BUYCOFFEE_URL);
  const patronite = publicSupportUrl(process.env.PATRONITE_URL);
  const progress = supportProgress();
  const pledgeV2 = process.env.SUPPORT_PLEDGE_V2 === 'true';
  const links = [
    { label: 'Wesprzyj miesięczny budżet', href: SUPPORT_LINKS.monthly },
    buycoffee && { label: 'Postaw kawę na BuyCoffee', href: buycoffee },
    patronite && { label: 'Wesprzyj projekt na Patronite', href: patronite },
  ].filter(Boolean) as { label: string; href: string }[];

  return <InfoPage eyebrow="WSPARCIE" title="Pomóż nam analizować kolejne wypowiedzi." longTitle lead="Wpłaty pomagają pokrywać koszty pobierania wpisów, analiz AI i utrzymania serwisu."
    actions={<Button href={SUPPORT_LINKS.monthly} variant="primary">Wesprzyj miesięczny budżet</Button>}>
    <p>Politycy mają spin doktorów. My mamy spin.clinic.</p>
    <section className="sc-support-pick" aria-label="Jak wesprzeć">
      <a className="sc-support-pick__opt" href={SUPPORT_LINKS.monthly}><b>Co miesiąc</b><span>Stały budżet Kliniki na zrzutka.pl. Nawet 20 zł miesięcznie to kilkanaście diagnoz.</span><em>Wesprzyj co miesiąc →</em></a>
      {buycoffee && <a className="sc-support-pick__opt" href={buycoffee}><b>Jednorazowo</b><span>Postaw kawę na BuyCoffee. Bez konta i bez zobowiązań.</span><em>Postaw kawę →</em></a>}
      <p className="sc-support-pick__note">Nie przyjmujemy pieniędzy od partii, polityków ani ich fundacji. Wpłata nie wpływa na wybór wpisów ani na wynik diagnozy.</p>
    </section>
    <section><h2>Kto za tym stoi</h2><p>Operatorem serwisu jest iapply sp. z o.o.; wsparcie czytelników pomaga finansować dalsze działanie. Kontakt: <a href="mailto:kontakt@spin.clinic">kontakt@spin.clinic</a>. <Link href="/o-nas#operator">Dane operatora</Link> · <Link href="/o-nas#kontakt">pozostałe kontakty</Link>.</p></section>
    <section><h2>Na co idą pieniądze</h2>
      <p>Finansujemy dostęp do wpisów na X, płatne etapy analizy, transkrypcje nagrań oraz serwer, bazę danych i kopie zapasowe. Część zadań korzysta z bezpłatnych limitów usług.</p>
      <dl className="sc-support-costs">{COSTS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
    </section>
    {progress ? <section aria-labelledby="support-goal-title"><h2 id="support-goal-title">Cel na ten miesiąc</h2>
      {/* Bez daty aktualizacji nie pokazujemy kwoty ani paska - mogłyby być nieaktualne (audyt 046) */}
      <p>Cel miesięczny: {progress.goal.toLocaleString('pl-PL')} zł. {progress.updated && progress.raised !== null ? `Zebrano: ${progress.raised.toLocaleString('pl-PL')} zł (stan na ${progress.updated}).` : 'Aktualna kwota zbiórki jest widoczna na stronie zbiórki.'}</p>
      {progress.updated && progress.percent !== null ? <div className="sc-support-goal" role="img" aria-label={`Zebrano ${progress.percent}% celu`}><div className="sc-support-goal__bar"><span style={{ width: `${progress.percent}%` }} /></div></div> : null}
    </section> : null}
    <section><h2>Na co zbieramy</h2><dl className="sc-support-costs">{GOALS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
      <p><a href={SUPPORT_LINKS.phase3}>Wesprzyj własny serwer AI na zrzutka.pl</a></p>
      <p><Link href="/o-nas#rozwoj">Trzy fazy projektu</Link></p>
    </section>
    <section><h2>Wsparcie nie kupuje wpływu</h2><p>{glueShortWords(pledgeV2 ? PLEDGE_V2 : PLEDGE_V1)}</p></section>
    <section><h2>Inne sposoby wsparcia</h2><p>Wpłaty obsługują zewnętrzne serwisy. spin.clinic nie przetwarza danych płatniczych. Zbiórka na miesięczny budżet nie jest subskrypcją.</p><ul>{links.filter(link => link.href !== SUPPORT_LINKS.monthly).map(link => <li key={link.href}><a href={link.href}>{link.label}</a></li>)}</ul><p>Możesz też udostępnić diagnozę z <Link href="/klinika">Kliniki</Link>.</p></section>
    <NewsletterSignup source="wsparcie" />
  </InfoPage>;
}
