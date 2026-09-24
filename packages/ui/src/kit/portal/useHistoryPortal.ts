"use client";

/**
 * useHistoryPortal — adres jest odbiciem stanu React, nigdy odwrotnie
 * (docs/UI_KIT_PLAN.md → «Портал» → «Адрес»).
 *
 * `window.history.pushState`/`replaceState`, NIGDY `router.push`: prawdziwa nawigacja App
 * Router ściągnie payload RSC segmentu i ZDEMONTUJE drzewo, w którym żyje karta-partner
 * morfingu. `scroll: false` by tu nie pomogło — problem jest w odmontowaniu.
 *
 * Adres ZAWSZE zachowuje `window.location.search` (tryb `query` dokłada/zdejmuje tylko
 * parametr `podglad`) — inaczej wyciek innych parametrów (np. `q` wyszukiwarki) po stronie
 * wywołującego (Baza→PortalHome) zresetowałby filtr w trakcie otwartego overlaya.
 *
 * Zamknięcie ZAWSZE idzie przez `history.back()`, gdy wpis należy do nas (`owned`) — krzyżyk
 * i przycisk „Wstecz” to dosłownie ten sam kod, a stos historii nie rośnie. Nawigacja
 * materiał→powiązany materiał używa `replaceState` (jedno „Wstecz” wraca na stronę główną,
 * a nie odwija łańcuch powiązanych).
 */

import { useCallback, useEffect, useRef } from "react";
import type { Article } from "../../types";
import type { PortalHistoryMode } from "./PortalProvider";

export type UseHistoryPortalOptions = {
  mode: PortalHistoryMode;
  /** Aktualnie otwarty materiał (faza `open`); `null` gdy zamknięty. */
  active: Article | null;
  /** = api.open — wywoływane przy powrocie z historii (Wstecz/Dalej, wejście z linku). */
  onOpen: (article: Article, originEl?: HTMLElement | null) => void;
  /** = api.close */
  onClose: () => void;
  /** Odnajduje Article po id wśród danych, którymi operuje sekcja/strona (fixtures na witrynie). */
  resolveArticle: (id: number) => Article | null | undefined | Promise<Article | null | undefined>;
};

export type HistoryPortal = {
  /** Krzyżyk/Escape/scrim/przeciągnięcie wywołują TO, nie `api.close()` bezpośrednio. */
  requestClose: () => void;
  /** Klik w powiązany materiał WEWNĄTRZ overlaya — `replaceState`, dokument.title, bez push. */
  replaceForRelated: (article: Article) => void;
};

function buildUrl(mode: PortalHistoryMode, id: number | null): string {
  const { pathname, search, hash } = window.location;
  if (mode === "path") {
    if (id === null) {
      const base = pathname.replace(/\/material\/-?\d+\/?$/, "") || "/";
      return `${base}${search}${hash}`;
    }
    return `/material/${id}${search}${hash}`;
  }
  const params = new URLSearchParams(search);
  if (id === null) params.delete("podglad");
  else params.set("podglad", String(id));
  const qs = params.toString();
  return `${pathname}${qs ? `?${qs}` : ""}${hash}`;
}

function readIdFromLocation(mode: PortalHistoryMode): number | null {
  if (mode === "path") {
    const match = window.location.pathname.match(/\/material\/(-?\d+)/);
    return match ? Number(match[1]) : null;
  }
  const raw = new URLSearchParams(window.location.search).get("podglad");
  return raw ? Number(raw) : null;
}

export function useHistoryPortal({ mode, active, onOpen, onClose, resolveArticle }: UseHistoryPortalOptions): HistoryPortal {
  const owned = useRef(false);
  const originalTitle = useRef<string | null>(null);
  const lastReflectedId = useRef<number | null>(null);
  // Ustawiane TUŻ przed onOpen()/onClose() wywołanym Z historii (popstate, wczytanie strony),
  // żeby efekt niżej (śledzący `active`) nie odbił tego z powrotem jako nowego pushState.
  const suppressReflect = useRef(false);

  // Wczytanie strony z już obecnym ?podglad=<id> (lub /material/<id>): otwórz bez morfingu
  // (PortalLayer renderuje przejście przez zanik — brak `flight`, bo originEl nie istnieje
  // w chwili wywołania) i podłącz nasłuch Wstecz/Dalej.
  useEffect(() => {
    if (mode === "none") return;
    let disposed = false;
    let request = 0;
    const openFromLocation = async (id: number) => {
      const currentRequest = ++request;
      const article = await resolveArticle(id);
      if (disposed || currentRequest !== request || !article) return false;
      suppressReflect.current = true;
      lastReflectedId.current = id;
      onOpen(article, null);
      return true;
    };

    const initialId = readIdFromLocation(mode);
    if (initialId !== null) void openFromLocation(initialId);

    function onPopState() {
      owned.current = false;
      const id = readIdFromLocation(mode);
      if (id !== null) {
        void openFromLocation(id).then((opened) => {
          if (!opened && !disposed) {
            suppressReflect.current = true;
            lastReflectedId.current = null;
            onClose();
          }
        });
        return;
      }
      suppressReflect.current = true;
      lastReflectedId.current = null;
      onClose();
    }
    window.addEventListener("popstate", onPopState);
    return () => { disposed = true; window.removeEventListener("popstate", onPopState); };
    // Zamierzenie: tylko `mode` — onOpen/onClose/resolveArticle to referencje wywołującego,
    // które nie powinny resetować nasłuchu przy każdym renderze.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // Odbija zmiany `active` (spowodowane KLIKNIĘCIEM, nie historią) w adresie i tytule.
  useEffect(() => {
    if (mode === "none") return;
    if (originalTitle.current === null) originalTitle.current = document.title;

    if (active) {
      document.title = active.title;
      if (suppressReflect.current) {
        suppressReflect.current = false;
        lastReflectedId.current = active.id;
        return;
      }
      if (lastReflectedId.current === active.id) return; // już w adresie (np. przez replaceForRelated)
      window.history.pushState({ scPortal: active.id }, "", buildUrl(mode, active.id));
      owned.current = true;
      lastReflectedId.current = active.id;
    } else {
      if (originalTitle.current !== null) document.title = originalTitle.current;
      if (suppressReflect.current) {
        suppressReflect.current = false;
        return;
      }
      lastReflectedId.current = null;
    }
  }, [active, mode]);

  const requestClose = useCallback(() => {
    if (mode === "none") {
      onClose();
      return;
    }
    if (owned.current) {
      window.history.back();
      return;
    }
    // Wpisu w historii nie ma — nie ma dokąd wracać (np. bezpośredni link z ?podglad=).
    suppressReflect.current = true;
    window.history.replaceState({}, "", buildUrl(mode, null));
    lastReflectedId.current = null;
    onClose();
  }, [mode, onClose]);

  const replaceForRelated = useCallback(
    (article: Article) => {
      if (mode === "none") return;
      window.history.replaceState({ scPortal: article.id }, "", buildUrl(mode, article.id));
      lastReflectedId.current = article.id;
      document.title = article.title;
    },
    [mode],
  );

  return { requestClose, replaceForRelated };
}
