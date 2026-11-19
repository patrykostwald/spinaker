import { NIEPEWNOSC } from './warstwy';
import { liczbaKomunikatow } from './powiaty';

/**
 * Komunikaty o stanie danych, każdy stan osobno (zlecenie Z6-poprawki, P1-2):
 *  - dane niedostępne (błąd albo zły format odpowiedzi): nigdy „brak komunikatów”,
 *  - dane obcięte (limit stron wpisów albo zdarzeń): pokazujemy najnowsze, starsze pominięto,
 *  - dane nieaktualne (ostatnie odświeżenie się nie udało, ale mamy wcześniejsze dane),
 *  - status niedostępny (zdarzenia): wpis dostaje „Status niedostępny”, nie „Komunikat bez zdarzenia”.
 *  - brak potwierdzenia warstw (recenzja PR #38, P2-7): wpisy z warstw nieobecnych w bieżącej, poprawnej odpowiedzi warstwy/ są ukryte.
 * „Brak komunikatów” pokazuje tylko ten, kto ma kompletną odpowiedź (patrz TerazPage, P1-3).
 */
export interface StanPobrania {
  /** Pierwsze pobranie jeszcze trwa. */
  ladowanie?: boolean;
  /** Błąd albo zły format, i nie ma żadnych wcześniejszych danych. */
  niedostepne: boolean;
  /** Błąd ostatniego odświeżenia, ale pokazujemy wcześniejsze dane. */
  nieaktualne?: boolean;
  /** Są jeszcze starsze rekordy poza limitem stron. */
  uciete?: boolean;
  /** Liczba rekordów o nieznanym formacie, pominiętych. */
  pominiete?: number;
  /** Ile rekordów faktycznie pobraliśmy (przy obcięciu mówimy, ile mamy). */
  pobrane?: number;
  /** Warstwy: liczba wpisów (także powiązanych ze zdarzeniami) ukrytych, bo ich warstwa nie jest potwierdzona w bieżącej odpowiedzi warstwy/. */
  niepotwierdzone?: number;
}

export interface KomunikatyDanychProps {
  /** Wpisy (pomijane w widoku „Mój powiat”, który ma własne komunikaty w sekcjach). */
  wpisy?: StanPobrania;
  warstwy: StanPobrania;
  zdarzenia: StanPobrania;
  /** Wybrany wpis (z adresu) nie istnieje w bieżących danych. */
  brakWybranego?: boolean;
}

export function KomunikatyDanych({ wpisy, warstwy, zdarzenia, brakWybranego }: KomunikatyDanychProps) {
  return <>
    {wpisy?.ladowanie && <p className="tz-komunikat" role="status">Wczytujemy komunikaty…</p>}
    {wpisy?.niedostepne && <p className="tz-komunikat tz-komunikat--blad" role="alert">
      <strong>Dane niedostępne.</strong> Nie udało się pobrać komunikatów, więc nie wiemy, co się dzieje: {NIEPEWNOSC}.</p>}
    {wpisy?.nieaktualne && <p className="tz-komunikat tz-komunikat--blad" role="status">Nie udało się odświeżyć komunikatów. Pokazujemy ostatnio pobrane, mogą być nieaktualne.</p>}
    {wpisy?.uciete && <p className="tz-komunikat tz-komunikat--mala" role="status">Dane obcięte: pobraliśmy {wpisy.pobrane !== undefined ? `${liczbaKomunikatow(wpisy.pobrane)}, najnowsze` : 'najnowsze komunikaty'}, starsze pominięto. Zawęź czas albo region.</p>}
    {!!wpisy?.pominiete && <p className="tz-komunikat tz-komunikat--mala" role="status">Pominięto komunikaty o nieznanym formacie: {wpisy.pominiete}.</p>}

    {zdarzenia.niedostepne && <p className="tz-komunikat tz-komunikat--blad" role="alert">
      <strong>Statusy niedostępne.</strong> Nie wiemy, które komunikaty są potwierdzone, a które odwołane. Sprawdź oryginał u źródła.</p>}
    {zdarzenia.nieaktualne && <p className="tz-komunikat tz-komunikat--mala" role="status">Nie udało się odświeżyć statusów komunikatów, mogą być nieaktualne.</p>}
    {zdarzenia.uciete && <p className="tz-komunikat tz-komunikat--mala" role="status">Statusy sprawdziliśmy tylko dla najnowszych zdarzeń. Starsze komunikaty oznaczamy jako „Status niedostępny”.</p>}
    {!!zdarzenia.pominiete && <p className="tz-komunikat tz-komunikat--mala" role="status">Pominięto zdarzenia o nieznanym formacie: {zdarzenia.pominiete}. Część statusów może być niedostępna.</p>}

    {warstwy.niedostepne && <p className="tz-komunikat tz-komunikat--blad" role="status">
      <strong>Lista warstw niedostępna.</strong> Nie możemy sprawdzić nazw źródeł ani tego, czy któraś warstwa została wyłączona.</p>}
    {warstwy.nieaktualne && !warstwy.niepotwierdzone && <p className="tz-komunikat tz-komunikat--blad" role="status">
      <strong>Lista warstw nieaktualna.</strong> Nie udało się jej odświeżyć, więc nie pokazujemy komunikatów z warstw bez aktualnego potwierdzenia: {NIEPEWNOSC}.</p>}
    {!!warstwy.niepotwierdzone && <p className="tz-komunikat tz-komunikat--blad" role="status">
      <strong>Warstwy niepotwierdzone.</strong> Nie mamy aktualnej listy warstw, więc ukrywamy komunikaty z warstw bez potwierdzenia ({warstwy.niepotwierdzone}): {NIEPEWNOSC}.</p>}
    {brakWybranego && <p className="tz-komunikat tz-komunikat--blad" role="status">Tego wpisu nie ma w bieżących danych (inny okres, region, warstwa wyłączona albo wpis wycofany). Zmień okres w panelu warstw.</p>}
  </>;
}
