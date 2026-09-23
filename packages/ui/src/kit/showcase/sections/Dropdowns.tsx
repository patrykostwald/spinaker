"use client";

/**
 * Witryna Dropdown — trzy tryby obok siebie, `multi` domyślnie otwarty,
 * plus instancja blisko dołu panelu do pokazania odwrócenia w górę.
 * docs/UI_KIT_PLAN.md → «Компоненты» (Dropdown), «Дропдаун».
 */

import { useState } from "react";
import { Dropdown, type DropdownItem } from "../../Dropdown";
import { Button } from "../../Button";

export const meta = {
  id: "dropdowny",
  title: "Dropdowny",
  lead: "Jedna implementacja, trzy tryby: menu (akcje) · single (jeden wybór) · multi (wiele, panel nie zamyka się na wyborze).",
};

const MENU_ITEMS: DropdownItem[] = [
  { value: "share", label: "Udostępnij w X" },
  { value: "export", label: "Eksportuj tekst" },
  { value: "report", label: "Zgłoś błąd", description: "Otwiera formularz zgłoszenia" },
  { value: "archive", label: "Zarchiwizuj", disabled: true },
];

const SOURCE_ITEMS: DropdownItem[] = [
  { value: "dziennik", label: "Dziennik Przykładowy" },
  { value: "serwis", label: "Serwis Testowy" },
  { value: "agencja", label: "Agencja Poglądowa" },
  { value: "biuletyn", label: "Biuletyn Makiety Regionalnej i Przykładowej" },
  { value: "instytut", label: "Instytut Przykładów", disabled: true },
];

const CATEGORY_ITEMS: DropdownItem[] = [
  { value: "artykuly", label: "Artykuły" },
  { value: "wywiady", label: "Wywiady" },
  { value: "glosowania", label: "Głosowania Sejmu" },
  { value: "factchecki", label: "Fact-checki" },
  { value: "podcasty", label: "Podcasty" },
];

function DropdownsPanel({ theme }: { theme: "dark" | "light" }) {
  const [single, setSingle] = useState("dziennik");
  const [multi, setMulti] = useState<string[]>(["wywiady", "factchecki"]);

  return (
    <div className="sc-specimen__theme sc-root" data-sc-theme={theme}>
      <p className="sc-t-caption">{theme === "dark" ? "Noc" : "Dzień"}</p>

      <h4 className="sc-t-title-s sc-section__sub">Trzy tryby</h4>
      <div style={{ display: "flex", gap: "var(--sc-s-4)", flexWrap: "wrap", alignItems: "flex-start" }}>
        <div>
          <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 6px" }}>menu</p>
          <Dropdown label="Działania" mode="menu" items={MENU_ITEMS} onSelect={() => {}} />
        </div>
        <div>
          <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 6px" }}>single</p>
          <Dropdown
            label={SOURCE_ITEMS.find((i) => i.value === single)?.label ?? "Źródło"}
            ariaLabel="Wybierz źródło"
            mode="single"
            items={SOURCE_ITEMS}
            value={single}
            onChange={(v) => setSingle(v as string)}
          />
        </div>
        {/* R0: otwarty panel jest absolutny — rezerwujemy pod nim miejsce, żeby nie nachodził na kolejne demo. */}
        <div style={{ minHeight: 380 }}>
          <p className="sc-t-caption sc-text-3" style={{ margin: "0 0 6px" }}>multi (domyślnie otwarty)</p>
          <Dropdown
            label={`Kategorie${multi.length ? ` (${multi.length})` : ""}`}
            ariaLabel="Filtruj po kategorii"
            mode="multi"
            items={CATEGORY_ITEMS}
            value={multi}
            onChange={(v) => setMulti(v as string[])}
            defaultOpen
            footer={
              <Button variant="quiet" size="sm" onClick={() => setMulti([])}>
                Wyczyść
              </Button>
            }
          />
        </div>
      </div>

      <h4 className="sc-t-title-s sc-section__sub">Wyrównanie i odwrócenie w górę</h4>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "0 0 var(--sc-s-3)" }}>
        Wyzwalacz blisko dolnej krawędzi widoku — panel powinien wyrosnąć w górę, nie zostać obcięty.
      </p>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Dropdown label="Sortuj" mode="menu" items={MENU_ITEMS} align="end" onSelect={() => {}} />
      </div>
      <div style={{ height: "70vh" }} aria-hidden="true" />
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Dropdown label="Filtry (dolna krawędź)" mode="menu" items={MENU_ITEMS} align="end" onSelect={() => {}} />
      </div>
    </div>
  );
}

export function Section() {
  return (
    <div className="sc-specimen">
      <DropdownsPanel theme="dark" />
      <DropdownsPanel theme="light" />
    </div>
  );
}
