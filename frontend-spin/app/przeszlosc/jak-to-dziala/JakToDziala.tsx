import { Bar, Foot, Icon } from '../ui';
import { Spis } from './Spis';
import { Standalone } from './Wyspa';
import {
  AI_PUNKTY, AKTUALIZACJA, BLEDY_KROKI, BRAKI, BRAKI_NIE_MAMY, KONTAKT, KROKI, LACZENIE, LACZENIE_NIE, LACZENIE_WZMIANKI, LACZENIE_ZNACZENIE,
  MIARA, OBIETNICA, PRZYPIS, PROGI, REDAKCJE, SCIEZKI, SEKCJE, ZASADA, ZRODLA, ZRODLA_UWAGA, nb,
} from './tresc';
import './jak-to-dziala.css';

/**
 * "Jak to działa" (przeszłość.today, seria PWA + "Jak to działa", 13.10.2026): jasna podstronka, na której wszystko jest opisane.
 * Strona statyczna (komponent serwerowy, bez API): jedna kolumna treści ok. 68 znaków i spis treści z kotwicami od 1100 px,
 * na telefonie spis na górze jako zawijane linki, tabela źródeł jako karty. Wyspy klienckie: pasek, stopka, spis, tryb strony.
 * Laws of UX: Miller i Chunking (9 sekcji, jedna myśl na akapit), Jakob (spis treści, tabela), Proximity i Common Region (grupy tłem,
 * bez ramek), Serial Position (obietnica na początku, sprostowania i kontakt na końcu), Tesler (system bierze złożoność łączenia).
 */
const sekcja = (id: string) => SEKCJE.find(s => s.id === id)!;

function Naglowek({ id }: { id: string }) {
  const s = sekcja(id);
  return <h2 id={s.id} className="jd-h2"><span className="jd-n" aria-hidden="true">{s.numer}</span>{s.tytul}</h2>;
}

function Lista({ items, className = 'jd-list' }: { items: string[]; className?: string }) {
  return <ul className={className}>{items.map(t => <li key={t}>{nb(t)}</li>)}</ul>;
}

/** Wycinki prawdziwego interfejsu (markup, nie obrazki): tylko etykiety, które są w aplikacji; bez danych konkretnych osób. */
function WycinekZapytanie() {
  return <div className="jd-ui" aria-hidden="true">
    <div className="jd-ui__modes"><span data-on="">Temat</span><span>Osoba</span><span>Spółka</span></div>
    <div className="jd-ui__field"><Icon name="search" /><span>CPK</span><span className="jd-ui__btn">Pokaż</span></div>
  </div>;
}
function WycinekWynik() {
  return <ul className="jd-ui jd-ui--nodes" aria-hidden="true">
    <li><span className="jd-ui__ic"><Icon name="person" /></span><span><b>Osoba publiczna</b><small>poseł, minister, urząd</small></span></li>
    <li className="d1"><span className="jd-ui__ic"><Icon name="statement" /></span><span><b>Co powiedziała</b><small>wpis na X, druk Sejmu, artykuł</small></span></li>
    <li className="d1"><span className="jd-ui__ic"><Icon name="organisation" /></span><span><b>Spółka lub fundacja (KRS)</b><small>gdzie zasiada: zarząd, rada</small></span></li>
  </ul>;
}
function WycinekZrodlo() {
  return <div className="jd-ui jd-ui--src" aria-hidden="true">
    <span className="jd-ui__row"><b>sejm.gov.pl</b><span>↗</span></span>
    <span className="jd-ui__row"><span>Zapisz kopię teraz</span></span>
    <span className="jd-ui__row"><span>Kopiuj przypis</span></span>
  </div>;
}
const WYCINKI = [<WycinekZapytanie key="1" />, <WycinekWynik key="2" />, <WycinekZrodlo key="3" />];

const NAGLOWKI_TABELI = ['Źródło', 'Co zawiera', 'Zakres i okres', 'Odświeżanie', 'Ograniczenia'] as const;
const tbc = (value: string) => value.startsWith('Do potwierdzenia');

export function JakToDziala() {
  return <div className="px pt-page jd">
    <Standalone />
    <Bar quiet />
    <div className="jd-wrap">
      <Spis items={SEKCJE} />
      <article className="jd-art" id="jd-tresc" aria-labelledby="jak">
        <header className="jd-sec jd-intro">
          <p className="px-kicker">Przeszłość publiczna ze źródłem</p>
          <h1 id="jak">Jak to działa</h1>
          <p className="jd-lead">{nb(OBIETNICA)}</p>
          <p className="jd-p jd-rule"><b>Zasada naczelna.</b> {nb(ZASADA)}</p>
          <div className="jd-act"><a className="px-btn" href="/przeszlosc#wynik">Zobacz przykład</a>
            <span>Temat dnia, z drzewem powiązań i źródłami.</span></div>
        </header>

        <section className="jd-sec" aria-labelledby="kroki"><Naglowek id="kroki" />
          <ol className="jd-steps">
            {KROKI.map((k, i) => <li key={k.n} className="jd-step">
              <div className="jd-step__t"><b aria-hidden="true">{k.n}</b><h3>{nb(k.tytul)}</h3><p>{nb(k.tekst)}</p></div>
              <figure className="jd-step__ui">{WYCINKI[i]}<figcaption>Przykład ilustracyjny, nie wynik wyszukiwania.</figcaption></figure>
            </li>)}
          </ol>
        </section>

        <section className="jd-sec" aria-labelledby="dane"><Naglowek id="dane" />
          <p className="jd-p">{nb('Każdy fakt w serwisie prowadzi do jednego z poniższych źródeł. Dane pobieramy automatycznie z rejestrów i serwisów publicznych. Tabela pokazuje, co z którego źródła bierzemy i czego nie obiecujemy.')}</p>
          <div className="jd-tbl" role="table" aria-label="Źródła danych przeszłość.today">
            <div className="jd-tbl__head" role="rowgroup"><div role="row">{NAGLOWKI_TABELI.map(h => <span key={h} role="columnheader">{h}</span>)}</div></div>
            <div role="rowgroup">{ZRODLA.map(z => <div key={z.nazwa} className="jd-tbl__row" role="row">
              <span role="rowheader" className="jd-tbl__name"><b>{nb(z.nazwa)}</b><small>{z.domena}</small></span>
              <span role="cell" data-l="Co zawiera">{nb(z.zawiera)}</span>
              <span role="cell" data-l="Zakres i okres" data-tbc={tbc(z.zakres) || undefined}>{nb(z.zakres)}</span>
              <span role="cell" data-l="Odświeżanie" data-tbc={tbc(z.odswiezanie) || undefined}>{nb(z.odswiezanie)}</span>
              <span role="cell" data-l="Ograniczenia">{nb(z.ograniczenia)}</span>
            </div>)}</div>
          </div>
          <p className="jd-note">{nb(ZRODLA_UWAGA)}</p>
        </section>

        <section className="jd-sec" aria-labelledby="laczenie"><Naglowek id="laczenie" />
          <p className="jd-p">{nb('Powiązania budujemy z identyfikatorów i dokumentów, nie z samego podobieństwa nazwisk. Zasady są trzy:')}</p>
          <Lista items={LACZENIE} />
          <p className="jd-p">{nb(LACZENIE_WZMIANKI)}</p>
          <div className="jd-two">
            <div className="jd-box"><h3>Co powiązanie oznacza</h3><Lista items={LACZENIE_ZNACZENIE} /></div>
            <div className="jd-box"><h3>Czego nie oznacza</h3><Lista items={LACZENIE_NIE} /></div>
          </div>
          <figure className="jd-paths">
            <figcaption>Przykład schematyczny: dwie ścieżki, każda z identyfikatorem i źródłem.</figcaption>
            {SCIEZKI.map(path => <ol key={path[0]} className="jd-path">{path.map((step, i) => <li key={step} data-end={i === path.length - 1 || undefined}>{nb(step)}</li>)}</ol>)}
          </figure>
        </section>

        <section className="jd-sec" aria-labelledby="miara"><Naglowek id="miara" />
          <Lista items={MIARA} />
          <p className="jd-p">{nb('Odstępstwa od klubu liczymy w kodzie, według definicji, a nie na podstawie czyjejś oceny. Te same progi obowiązują każdy klub:')}</p>
          <dl className="jd-def">{PROGI.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{nb(v)}</dd></div>)}</dl>
          <p className="jd-p">{nb('Głos inny niż większość klubu wynika z definicji i nie jest zarzutem; nie podajemy jego przyczyn.')}</p>
          <p className="jd-more"><a className="px-link" href="/przeszlosc/odstepstwa">Odstępstwa od klubu&nbsp;→</a></p>
        </section>

        <section className="jd-sec" aria-labelledby="ai"><Naglowek id="ai" />
          <Lista items={AI_PUNKTY} />
        </section>

        <section className="jd-sec" aria-labelledby="braki"><Naglowek id="braki" />
          <p className="jd-p">{nb('Brak w serwisie to nie to samo co brak w rzeczywistości. Tak czytaj luki:')}</p>
          <Lista items={BRAKI} />
          <p className="jd-p">{nb(BRAKI_NIE_MAMY)}</p>
        </section>

        <section className="jd-sec" aria-labelledby="bledy"><Naglowek id="bledy" />
          <p className="jd-p">{nb('Pomyłki się zdarzają. Poprawiamy je jawnie i ze źródłem:')}</p>
          <ol className="jd-list jd-list--n">{BLEDY_KROKI.map(t => <li key={t}>{nb(t)}</li>)}</ol>
          <p className="jd-p">{nb(`Pytania o dane osobowe i sprzeciw kieruj na ${KONTAKT} (procedura i terminy odpowiedzi: do potwierdzenia).`)}</p>
          <p className="jd-more"><a className="px-link" href="/przeszlosc/poprawki">Rejestr poprawek&nbsp;→</a></p>
        </section>

        <section className="jd-sec" aria-labelledby="redakcje"><Naglowek id="redakcje" />
          <p className="jd-p">{nb('Wszystko, co widzisz, możesz zabrać do własnej analizy i sprawdzić w oryginale:')}</p>
          <Lista items={REDAKCJE} />
          <p className="jd-p">{nb('Przykład przypisu do cytowania:')}</p>
          <blockquote className="jd-cite">{PRZYPIS}</blockquote>
          <p className="jd-p">{nb(`Kontakt dla redakcji i badaczy: ${KONTAKT}. Zespołom pomagamy we wdrożeniu; warunki po becie ustalamy indywidualnie, te same dla wszystkich.`)}</p>
          <p className="jd-more"><a className="px-link" href="/przeszlosc/funkcje">Co potrafi przeszłość.today&nbsp;→</a>
            <a className="px-link" href={`mailto:${KONTAKT}?subject=przeszłość.today`}>Napisz do nas&nbsp;→</a></p>
        </section>

        <p className="jd-stan">{nb('Treść tej strony: stan na')} <time dateTime="2026-10-13">{AKTUALIZACJA}</time>. {nb('Operator: iapply sp. z o.o., Poznań.')}</p>
      </article>
    </div>
    <Foot />
  </div>;
}
