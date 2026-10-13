/**
 * Landing profilu osoby "Najważniejsze" (przeszłość.today, port v3, 13.10.2026): funkcje czyste, bez Reacta i DOM.
 * Z danych profilu (GET /api/przeszlosc/osoba/<ident>/) budują kafle: podmioty z KRS, oświadczenia majątkowe, kilometrówki
 * i rozliczenia, głosy inne niż większość klubu, funkcje, media. NIE wymyślają pól ani liczb: czego brak w danych, to stan "brak w naszych
 * danych" z zakresem i datą. Testy: tests/121-przeszlosc-najwazniejsze.test.cjs. Bez importów (ładowane przez transpileModule).
 */

/* ---------------------------------------------------------------- wejście (podzbiór odpowiedzi profilu) */

export type LandingOrg = {
  id: number; name: string; krs_number: string; official_register_url?: string; extra_register_url?: string;
  public_role?: string; organ?: string; relation_status?: string; since?: string | null; until?: string | null;
  kind?: string; legal_form?: string; verified_at?: string | null;
};
export type LandingMoney = null | { results: { url?: string; contracts?: { count?: number }; grants?: { count?: number } }[] };
export type LandingInput = {
  generated_at: string;
  source_checked_at?: string;
  official_profile_url?: string;
  access?: { locked?: string[] } | null;
  organisations?: LandingOrg[];
  money_trail?: LandingMoney | undefined;
  committees?: { code: string; name: string; role?: string; since?: string | null; url?: string }[];
  employment_timeline?: { position: string; organisation?: string; status?: string; since?: string | null; until?: string | null; checked_at?: string | null; source?: { url?: string } }[];
  documents?: { by_kind?: Record<string, number>; results?: { kind?: string; label?: string; title?: string; date?: string | null; url?: string }[] };
  votes?: { available?: boolean; count?: number; deviation?: null | { term: number; club: string; share: number; club_median: number | null; flagged: boolean; counted: number; rebellions_total: number; latest: null | { url: string; title?: string; date: string | null } } };
  open_data?: null | {
    mp_expenses?: { mileage?: { period: string; amount_pln: number | null; km: number | null; check?: string; origin?: string; origin_url?: string }[];
      offices?: { year: number; total_pln: number | null; pdf_url?: string; check?: string }[] };
    ep_integrity?: { declarations?: { title: string; url: string }[]; income?: null | { total_eur: number; paid: number };
      meetings?: { count: number } };
  };
  materials?: { count?: number };
  mentions?: { total?: number };
  articles_total?: number;
  posts?: { count?: number };
};

/* ---------------------------------------------------------------- wyjście */

export type TileId = 'podmioty' | 'majatek' | 'km' | 'klub' | 'funkcje' | 'media';
export type SourceRef = { label: string; url: string | null };
export type OrgRow = { key: string; name: string; href: string | null; krs: string; krsUrl: string | null; type: string; role: string; period: string; status: 'current' | 'former'; statusText: string };
export type DocRow = { key: string; title: string; url: string | null; year: number | null };
export type Tile = {
  id: TileId;
  anchor: string;                  // id elementu kafla (kotwica indeksu)
  label: string;
  state: 'ok' | 'empty' | 'locked';
  value: string;                   // duża liczba albo stan ("brak w naszych danych")
  unit: string;                    // jedna linia pod liczbą
  lines: string[];                 // 1-3 linie wyjaśnienia
  orgs: OrgRow[];                  // tylko kafel podmiotów
  docs: DocRow[];                  // tylko kafel oświadczeń
  extra: { text: string; href: string } | null; // tylko kafel podmiotów: zamówienia i dotacje
  source: SourceRef[];
  stamp: string | null;            // ISO (data) odświeżenia
  stampText: string;               // "stan na 13.10.2026"
  link: { href: string; label: string; filter: 'record' | 'vote' | null };
};

/* ---------------------------------------------------------------- narzędzia */

export const NO_DATA = 'brak w naszych danych';
export const SHOWN_ORGS = 5;
export const LANDING_TITLE = 'Dane w jednym miejscu';
/** Zasada naczelna (właściciel 13.10, korekta): jedno widoczne zdanie nad sekcją; skrócona forma w stopce profilu i na stronie "Jak to działa". */
export const LANDING_RULE = 'To narzędzie pokazuje powiązane dane publiczne. Nie ocenia osób i nie wyciąga wniosków: wnioski należą do Ciebie. Powiązanie w danych nie jest zarzutem.';
export const LANDING_RULE_SHORT = 'Pokazujemy powiązane dane publiczne; nie oceniamy osób, wnioski należą do Ciebie. Powiązanie w danych nie jest zarzutem.';

/** Polska typografia: jednoliterowe słowa nie zostają na końcu wiersza (twarda spacja). */
export const nb = (text: string) => {
  const re = /(^|[\s(„])([aiouwzAIOUWZ])[ 	]+/g;
  let out = text;
  for (let i = 0; i < 4; i++) { const next = out.replace(re, '$1$2' + String.fromCharCode(160)); if (next === out) break; out = next; } // powtarzane: "i w" (jedna spacja jest wspólna)
  return out;
};
export const plural = (n: number, one: string, few: string, many: string) =>
  n === 1 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many;
/** Liczba po polsku z twardą spacją tysięcy (bez Intl: stabilna w każdym środowisku). */
export function num(v: number, digits = 0): string {
  const fixed = Math.abs(v).toFixed(digits);
  const [i, f] = fixed.split('.');
  const grouped = i.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${v < 0 ? '-' : ''}${grouped}${f && Number(f) !== 0 ? ',' + f : ''}`;
}
const pct = (v: number) => `${num(v, 1)}%`;
const pln = (v: number) => `${num(Math.round(v))} zł`;
const eur = (v: number) => `${num(Math.round(v))} €`;
/** "2026-10-13T06:29+00:00" -> "13.10.2026"; coś innego -> ''. */
export function ymd(iso?: string | null): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  return m ? `${m[3]}.${m[2]}.${m[1]}` : '';
}
const year = (iso?: string | null) => (/^\d{4}/.test(iso ?? '') ? (iso as string).slice(0, 4) : '');
const maxIso = (list: (string | null | undefined)[]) => list.filter((x): x is string => Boolean(x) && /^\d{4}-\d{2}-\d{2}/.test(x as string)).sort().pop() ?? null;

/** Adres z danych zewnętrznych: tylko http(s) albo ścieżka w serwisie (bez //); inaczej null. */
export function safeUrl(u: unknown): string | null {
  if (typeof u !== 'string') return null;
  const s = u.trim();
  if (/^https?:\/\/[^\s]+$/i.test(s)) return s;
  return /^\/(?!\/)[^\s]*$/.test(s) ? s : null;
}
export function hostOf(u?: string | null): string {
  try { return u ? new URL(u).hostname.replace(/^(www|api)\./, '') : ''; } catch { return ''; }
}
const sourceRef = (url?: string | null, label?: string): SourceRef | null => {
  const safe = safeUrl(url);
  const text = label || hostOf(safe);
  return text ? { label: text, url: safe } : null;
};
const uniqueSources = (list: (SourceRef | null)[]): SourceRef[] => {
  const seen = new Set<string>(); const out: SourceRef[] = [];
  for (const s of list) { if (!s) continue; if (!seen.has(s.label)) { seen.add(s.label); out.push(s); } }
  return out;
};

const LOCKED = (d: LandingInput, key: string) => Boolean(d.access?.locked?.includes(key));
const stampText = (verb: string, iso: string | null) => (iso ? `${verb} ${ymd(iso)}` : `${verb}: ${NO_DATA}`);

const SEJM_SRC = (): SourceRef => ({ label: 'sejm.gov.pl', url: 'https://www.sejm.gov.pl/' });
const INFO_LINK: Tile['link'] = { href: '/przeszlosc/jak-to-dziala', label: 'Skąd te dane →', filter: null };
function emptyTile(id: TileId, anchor: string, label: string, scope: string, stamp: string | null, link: Tile['link'], src: SourceRef | null = null): Tile {
  return { id, anchor, label, state: 'empty', value: NO_DATA, unit: '', lines: [nb(`Zakres: ${scope}.`)],
    orgs: [], docs: [], extra: null, source: src ? [src] : [], stamp, stampText: stampText('stan na', stamp), link };
}

/* ---------------------------------------------------------------- kafel 1: fundacje i spółki (KRS) */

const KIND_TYPE: Record<string, string> = { foundation: 'fundacja', association: 'stowarzyszenie', company: 'spółka' };
const KRS_RE = /^\d{10}$/;

/** Rodzaj podmiotu słowami z danych: fundacja, stowarzyszenie, spółka; inne = forma prawna z rejestru. */
export function orgType(o: LandingOrg): string {
  const known = KIND_TYPE[o.kind ?? ''];
  if (known) return known;
  const legal = (o.legal_form ?? '').trim();
  return legal || 'inny podmiot';
}
export function orgPeriod(o: LandingOrg): string {
  const from = year(o.since), to = year(o.until);
  if (o.relation_status === 'former') return from && to ? (from === to ? from : `${from} - ${to}`) : to ? `do ${to}` : from ? `od ${from}` : 'daty: brak w naszych danych';
  return from ? `od ${from}` : 'obecnie';
}
/** Obecne najpierw, potem według daty końca (albo początku) malejąco; stabilnie po nazwie. */
export function sortOrgs(list: LandingOrg[]): LandingOrg[] {
  const cur = (o: LandingOrg) => (o.relation_status === 'former' ? 0 : 1);
  return [...list].sort((a, b) => cur(b) - cur(a) || (b.until || b.since || '').localeCompare(a.until || a.since || '') || a.name.localeCompare(b.name, 'pl'));
}
export function orgRow(o: LandingOrg): OrgRow {
  const former = o.relation_status === 'former';
  const krs = KRS_RE.test(o.krs_number ?? '') ? o.krs_number : '';
  return {
    key: `${o.id}-${o.public_role ?? ''}-${o.relation_status ?? ''}`, name: o.name, href: krs ? `/przeszlosc/spolka/${krs}` : null, krs,
    krsUrl: safeUrl(o.extra_register_url) ?? safeUrl(o.official_register_url),
    type: orgType(o), role: (o.public_role || o.organ || '').trim(), period: orgPeriod(o),
    status: former ? 'former' : 'current', statusText: former ? 'wcześniej' : 'obecnie',
  };
}
export function kindsLine(list: LandingOrg[]): string {
  const c = { foundation: 0, association: 0, company: 0, other: 0 };
  for (const o of list) { const k = o.kind === 'foundation' || o.kind === 'association' || o.kind === 'company' ? o.kind : 'other'; c[k]++; }
  const parts: string[] = [];
  if (c.foundation) parts.push(`${c.foundation} ${plural(c.foundation, 'fundacja', 'fundacje', 'fundacji')}`);
  if (c.association) parts.push(`${c.association} ${plural(c.association, 'stowarzyszenie', 'stowarzyszenia', 'stowarzyszeń')}`);
  if (c.company) parts.push(`${c.company} ${plural(c.company, 'spółka', 'spółki', 'spółek')}`);
  if (c.other) parts.push(`${c.other} ${plural(c.other, 'inny podmiot', 'inne podmioty', 'innych podmiotów')}`);
  return parts.join(' · ');
}
function moneyExtra(d: LandingInput): Tile['extra'] {
  if (LOCKED(d, 'money_trail') || d.money_trail == null || !d.money_trail.results?.length) return null;
  const total = d.money_trail.results.reduce((a, r) => a + (r.contracts?.count ?? 0) + (r.grants?.count ?? 0), 0);
  return { text: nb(total > 0
    ? `Zamówienia publiczne i dotacje UE tych podmiotów (łączone po NIP i KRS): ${total}.`
    : 'Zamówienia publiczne i dotacje UE tych podmiotów w naszych danych: 0.'), href: '#pp-pieniadze' };
}
export function podmiotyTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const link = { href: '#pp-krs', label: 'Zobacz wszystko →', filter: null } as Tile['link'];
  if (LOCKED(d, 'krs')) return { ...emptyTile('podmioty', 'pt-t-podmioty', 'Fundacje i spółki powiązane w KRS', '', stamp, { href: '/przeszlosc/pilot', label: 'Pilotaż →', filter: null }),
    state: 'locked', value: 'w pilotażu', lines: [nb('Funkcje w KRS są w pilotażu przeszłość.today.')] };
  const list = sortOrgs(d.organisations ?? []);
  if (!list.length) return emptyTile('podmioty', 'pt-t-podmioty', 'Fundacje i spółki powiązane w KRS',
    'funkcje w organach fundacji, stowarzyszeń i spółek z KRS (osoby publiczne z naszej bazy)', stamp, link,
    { label: 'KRS (Ministerstwo Sprawiedliwości)', url: 'https://wyszukiwarka-krs.ms.gov.pl/' });
  const cur = list.filter(o => o.relation_status !== 'former').length;
  const verified = maxIso(list.map(o => o.verified_at));
  const first = list.find(o => safeUrl(o.official_register_url));
  return {
    id: 'podmioty', anchor: 'pt-t-podmioty', label: 'Fundacje i spółki powiązane w KRS', state: 'ok', value: String(list.length),
    unit: plural(list.length, 'podmiot powiązany po KRS', 'podmioty powiązane po KRS', 'podmiotów powiązanych po KRS'),
    lines: [[cur ? `obecnie: ${cur}` : '', list.length - cur ? `wcześniej: ${list.length - cur}` : '', kindsLine(list)].filter(Boolean).join(' · ')].filter(Boolean),
    orgs: list.map(orgRow), docs: [], extra: moneyExtra(d),
    source: uniqueSources([sourceRef(first?.official_register_url, 'KRS (Ministerstwo Sprawiedliwości)')]),
    stamp: verified ?? stamp, stampText: stampText(verified ? 'sprawdzono' : 'stan na', verified ?? stamp),
    link: { ...link, label: list.length > SHOWN_ORGS ? `Zobacz wszystko (${list.length}) →` : 'Zobacz wszystko →' },
  };
}

/* ---------------------------------------------------------------- kafel 2: oświadczenia majątkowe */

export const ASSET_LABEL = 'Oświadczenie majątkowe';
const ASSET_KINDS = ['asset_document', 'asset_declaration'];
/** Rok z tytułu dokumentu, tylko gdy jest jednoznaczny (jedna różna wartość 20xx). */
export function assetYear(title?: string | null): number | null {
  const years = new Set<string>();
  const re = /(^|\D)(20\d{2})(?!\d)/g;
  for (let m = re.exec(title ?? ''); m; m = re.exec(title ?? '')) years.add(m[2]);
  return years.size === 1 ? Number([...years][0]) : null;
}
export function majatekTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const link = { href: '#pp-os', label: 'Zobacz wszystko →', filter: 'record' } as Tile['link'];
  const results = d.documents?.results ?? [];
  const docsRaw = results.filter(r => ASSET_KINDS.includes(r.kind ?? '') || r.label === ASSET_LABEL);
  const count = Math.max(d.documents?.by_kind?.[ASSET_LABEL] ?? 0, docsRaw.length);
  const isMp = Boolean(d.votes?.available);
  if (!count) return emptyTile('majatek', 'pt-t-majatek', 'Oświadczenia majątkowe',
    isMp ? 'indeks oświadczeń posłów w serwisie Sejmu'
      : 'indeks oświadczeń posłów w serwisie Sejmu; osoba nie jest posłem w naszych danych', stamp, INFO_LINK,
    sourceRef(d.official_profile_url, 'sejm.gov.pl') ?? SEJM_SRC());
  const docs: DocRow[] = docsRaw.slice(0, 3).map((r, i) => ({ key: `${i}-${r.url ?? r.title ?? ''}`, title: (r.title ?? '').trim() || ASSET_LABEL, url: safeUrl(r.url), year: assetYear(r.title) }));
  const years = docs.map(x => x.year).filter((y): y is number => y !== null);
  const newest = years.length ? Math.max(...years) : null;
  return {
    id: 'majatek', anchor: 'pt-t-majatek', label: 'Oświadczenia majątkowe', state: 'ok', value: String(count),
    unit: `${plural(count, 'oświadczenie', 'oświadczenia', 'oświadczeń')} w indeksie Sejmu`,
    lines: [newest ? `Najnowsze w indeksie: za rok ${newest}.` : '', 'Odnośniki do skanów w serwisie Sejmu; kwot nie odczytujemy.'].filter(Boolean),
    orgs: [], docs, extra: null,
    source: uniqueSources([sourceRef(d.official_profile_url) ?? sourceRef('https://www.sejm.gov.pl/', 'sejm.gov.pl')]),
    stamp, stampText: stampText('stan na', stamp), link,
  };
}

/* ---------------------------------------------------------------- kafel 3: kilometrówki i rozliczenia */

export function kmTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const ex = d.open_data?.mp_expenses;
  const mileage = [...(ex?.mileage ?? [])].filter(m => m.amount_pln !== null && m.amount_pln !== undefined).sort((a, b) => String(b.period).localeCompare(String(a.period)));
  const offices = [...(ex?.offices ?? [])].filter(o => o.total_pln !== null && o.total_pln !== undefined).sort((a, b) => b.year - a.year);
  if (mileage.length || offices.length) {
    const m = mileage[0], o = offices[0];
    const unchecked = o && /nie sprawdzono/i.test(o.check ?? '') ? ' (PDF bez kontroli automatycznej)' : '';
    const lines: string[] = [];
    if (m) {
      lines.push(m.km !== null && m.km !== undefined ? `Przebieg: ${num(m.km)} km za rok ${m.period}.` : `Przebieg za rok ${m.period}: ${NO_DATA}.`);
      if (o) lines.push(`Biuro poselskie ${o.year}: ${pln(o.total_pln as number)}${unchecked}.`);
    } else lines.push(`Kilometrówki: ${NO_DATA}.${unchecked ? ' Biuro poselskie' + unchecked + '.' : ''}`);
    return {
      id: 'km', anchor: 'pt-t-km', label: 'Rozliczenia (kilometrówki)', state: 'ok',
      value: m ? pln(m.amount_pln as number) : pln(o!.total_pln as number),
      unit: m ? `kilometrówka za rok ${m.period}` : `biuro poselskie ${o!.year}`,
      lines: lines.map(nb), orgs: [], docs: [], extra: null,
      source: uniqueSources([m ? sourceRef(m.origin_url, m.origin_url ? undefined : m.origin) : null, o?.pdf_url ? sourceRef(o.pdf_url, 'sejm.gov.pl (PDF)') : null]),
      stamp, stampText: stampText('stan na', stamp), link: { href: '#pp-exp-h', label: 'Zobacz wszystko →', filter: null },
    };
  }
  const ep = d.open_data?.ep_integrity;
  if (ep && (ep.income || (ep.meetings?.count ?? 0) > 0 || (ep.declarations?.length ?? 0) > 0)) {
    const lines: string[] = [];
    if (ep.income) lines.push(`Płatne działania w deklaracji: ${ep.income.paid}.`);
    if (ep.meetings) lines.push(`Spotkania z lobbystami: ${ep.meetings.count}.`);
    return {
      id: 'km', anchor: 'pt-t-km', label: 'Rozliczenia (deklaracja PE)', state: 'ok',
      value: ep.income ? eur(ep.income.total_eur) : NO_DATA,
      unit: ep.income ? 'dochody dodatkowe z deklaracji' : 'deklaracja bez kwoty dochodów',
      lines: lines.map(nb), orgs: [], docs: [], extra: null,
      source: uniqueSources([sourceRef(ep.declarations?.[0]?.url), sourceRef('https://www.integritywatch.eu/about.php', 'integritywatch.eu')]),
      stamp, stampText: stampText('stan na', stamp), link: { href: '#pp-iw-h', label: 'Zobacz wszystko →', filter: null },
    };
  }
  const isMp = Boolean(d.votes?.available);
  return emptyTile('km', 'pt-t-km', 'Rozliczenia (kilometrówki)',
    isMp ? 'kilometrówki i wydatki biura poselskiego posłów na Sejm'
      : 'kilometrówki i wydatki biura posłów na Sejm; osoba nie jest posłem w naszych danych', stamp, INFO_LINK, SEJM_SRC());
}

/* ---------------------------------------------------------------- kafel 4: głosy inne niż większość klubu */

export function klubTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const link = { href: '#pp-os', label: 'Zobacz wszystko →', filter: 'vote' } as Tile['link'];
  const dev = d.votes?.deviation;
  if (!dev) return emptyTile('klub', 'pt-t-klub', 'Głosy inne niż większość klubu',
    d.votes?.available ? 'głosowania imienne Sejmu, zestawienie z klubem liczone co noc dla posłów z co najmniej 20 głosami'
      : 'głosowania imienne Sejmu; osoba nie jest posłem w naszych danych', stamp, INFO_LINK, SEJM_SRC());
  // tylko fakty i metoda w podpisie: liczba głosów innych niż większość klubu przy zgodności klubu >= 80% oraz udział wszystkich takich głosów
  const lines = [nb(`Wszystkie głosy inne niż większość klubu ${dev.club}: ${pct(dev.share)} z ${num(dev.counted)} głosowań w ${dev.term}. kadencji.`)];
  return {
    id: 'klub', anchor: 'pt-t-klub', label: 'Głosy inne niż większość klubu', state: 'ok', value: String(dev.rebellions_total),
    unit: 'przy zgodności klubu ≥ 80%',
    lines, orgs: [], docs: [], extra: null,
    source: uniqueSources([sourceRef(dev.latest?.url) ?? SEJM_SRC()]),
    stamp, stampText: stampText('stan na', stamp), link,
  };
}

/* ---------------------------------------------------------------- kafel 5: funkcje (komisje i mandaty) */

const LEAD = /przewodnicz|zastępc|zastępcz|sekretarz/i;
/** Mandat parlamentarny (Sejm, Senat, PE) przed innymi funkcjami: to on mówi, kim osoba jest w państwie. */
const isMandate = (e: { position: string; organisation?: string; source?: { url?: string } }) =>
  /^(poseł|posłanka|senator|prezydent)/i.test(e.position) || /(sejm|senat|europarl)/i.test(hostOf(e.source?.url));
export function funkcjeTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const link = { href: '#pp-funkcje', label: 'Zobacz wszystko →', filter: null } as Tile['link'];
  const current = (d.employment_timeline ?? []).filter(e => e.status === 'current');
  const com = d.committees ?? [];
  if (!current.length && !com.length) return emptyTile('funkcje', 'pt-t-funkcje', 'Funkcje',
    'aktualne mandaty, funkcje publiczne i komisje sejmowe z oficjalnych źródeł', stamp, INFO_LINK, SEJM_SRC());
  const lead = com.find(c => LEAD.test(c.role ?? ''));
  const lines: string[] = [];
  const main = current.find(isMandate) ?? current[0];
  if (main) lines.push(nb(`${main.position}${main.organisation ? `, ${main.organisation}` : ''}${main.since ? `, od ${year(main.since)}` : ''}.`));
  if (lead) lines.push(nb(`${lead.role}: ${lead.name}.`));
  else if (current.length > 1) lines.push(nb(`Obecnych funkcji publicznych: ${current.length}.`));
  const checked = maxIso([...current.map(e => e.checked_at), d.source_checked_at]);
  const useCom = com.length > 0;
  return {
    id: 'funkcje', anchor: 'pt-t-funkcje', label: 'Funkcje', state: 'ok',
    value: String(useCom ? com.length : current.length),
    unit: useCom ? plural(com.length, 'komisja sejmowa', 'komisje sejmowe', 'komisji sejmowych') : plural(current.length, 'obecna funkcja', 'obecne funkcje', 'obecnych funkcji'),
    lines, orgs: [], docs: [], extra: null,
    source: uniqueSources([sourceRef(main?.source?.url), com[0]?.url ? sourceRef(com[0].url) : null]),
    stamp: checked ?? stamp, stampText: stampText(checked ? 'sprawdzono' : 'stan na', checked ?? stamp), link,
  };
}

/* ---------------------------------------------------------------- kafel 6 (pasek): media i wpisy */

export function mediaTile(d: LandingInput): Tile {
  const stamp = d.generated_at;
  const link = { href: '#pp-media', label: 'Zobacz wszystko →', filter: null } as Tile['link'];
  const articles = d.articles_total ?? d.mentions?.total ?? d.materials?.count ?? 0;
  const confirmed = d.materials?.count ?? 0;
  const posts = d.posts?.count ?? 0;
  if (!articles && !posts) return emptyTile('media', 'pt-t-media', 'Wpisy i media', 'artykuły i wzmianki w mediach oraz wpisy na oficjalnych kontach X', stamp, link);
  return {
    id: 'media', anchor: 'pt-t-media', label: 'Wpisy i media', state: 'ok', value: num(articles),
    unit: plural(articles, 'artykuł lub wzmianka', 'artykuły lub wzmianki', 'artykułów i wzmianek'),
    lines: [`potwierdzonych: ${num(confirmed)} · wpisów na X: ${num(posts)}`], orgs: [], docs: [], extra: null,
    source: [{ label: 'media i konta oficjalne', url: null }],
    stamp, stampText: stampText('stan na', stamp), link,
  };
}

/* ---------------------------------------------------------------- całość */

export type Landing = {
  tiles: Tile[];                   // kolejność: podmioty, majątek, km, klub, funkcje, media
  lean: boolean;                   // brak podmiotów: kafel 1 niższy, kafle 4-5 po dwie kolumny
  stamp: string | null;
  sources: SourceRef[];
  disclaimer: string;
};
export function buildLanding(d: LandingInput): Landing {
  const tiles = [podmiotyTile(d), majatekTile(d), kmTile(d), klubTile(d), funkcjeTile(d), mediaTile(d)];
  return {
    tiles, lean: tiles[0].state !== 'ok', stamp: d.generated_at ?? null,
    sources: uniqueSources(tiles.flatMap(t => t.source).filter(s => s.url).map(s => ({ ...s, label: s.label.replace(/\s*\(PDF\)$/, '') }))),
    disclaimer: LANDING_RULE,
  };
}

/** Spis sekcji profilu (zastępuje wiersz indeksu akt): kafle landingu najpierw, potem sekcje dotychczasowe. Bez "Media": pasek mediów
 *  jest ostatnim kafelkiem landingu, a dziewięć pozycji mieści się w jednym wierszu. */
export function landingIndex(o: { hasDenominators: boolean; hasNet: boolean; hasPairs?: boolean }): [string, string][] {
  return [
    ['pt-t-podmioty', 'Fundacje i spółki'], ['pt-t-majatek', 'Oświadczenia'], ['pt-t-km', 'Rozliczenia'], ['pt-t-klub', 'Głosowania'],
    ['pt-t-funkcje', 'Funkcje'], ['pp-zrodla', 'Źródła'],
    // „Wcześniej i teraz” (flaga par, tylko gdy API zwraca pary): sekcja z pełną listą tuż nad osią czasu; skrót "Wcześniej", żeby
    // dziesięć pozycji (z siecią i mianownikami) mieściło się w jednym wierszu spisu przy 1088 px
    ...(o.hasPairs ? [['wczesniej-i-teraz', 'Wcześniej'] as [string, string]] : []),
    ['pp-os', 'Oś czasu'],
    ...(o.hasDenominators && o.hasNet ? [['pp-siec', 'Sieć'] as [string, string]] : []),
    ...(o.hasDenominators ? [['dn', 'Mianowniki'] as [string, string]] : []),
  ];
}
