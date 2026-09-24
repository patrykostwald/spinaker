"use client";

/**
 * Witryna ThreadView — dwa układy nitki (dwie kolumny / jeden rząd) na fikcyjnej nitce z fikstur,
 * w obu motywach. Przełącznik zapamiętuje wybór osobno dla witryny (`storageKey`).
 */

import { ThreadView } from "../../ThreadView";
import { FIXTURE_STRIPS } from "../fixtures";
import type { ThreadItem } from "../../../types";

export const meta = {
  id: "nitka",
  title: "Nitka",
  lead: "ThreadView: dwie kolumny (materiał otwierający + przewijana lista z datami) albo jeden rząd na całą szerokość z przewijaniem poziomym. Przejście między układami — morfing tych samych kart.",
};

const ITEMS: ThreadItem[] = FIXTURE_STRIPS[1].articles.map((article, index) => ({
  id: -(9000 + index),
  position: index + 1,
  editorial_note: index === 0 ? "Komentarz redakcyjny do materiału otwierającego (przykład)." : index === 3 ? "Krótka uwaga autora nitki (przykład)." : "",
  author_name: "Redakcja Przykładowa",
  author_role: "editor",
  article,
}));

function Panel({ theme }: { theme: "dark" | "light" }) {
  return (
    <div className="sc-specimen__theme sc-root" data-sc-theme={theme}>
      <p className="sc-t-caption">{theme === "dark" ? "Noc" : "Dzień"}</p>
      <ThreadView items={ITEMS} anchorFirst storageKey={`sc-showcase-thread-layout-${theme}`} defaultLayout={theme === "dark" ? "columns" : "row"} />
    </div>
  );
}

export function Section() {
  return (
    <div className="sc-specimen sc-specimen--stack">
      <Panel theme="dark" />
      <Panel theme="light" />
    </div>
  );
}
