"use client";

import { type ReactNode, useState } from "react";
import { Checkbox } from "../../Checkbox";
import { Radio, RadioGroup } from "../../Radio";
import { Switch } from "../../Switch";
import { Segmented } from "../../Segmented";
import { SearchField } from "../../SearchField";

export const meta = {
  id: "kontrolki",
  title: "Kontrolki",
  lead: "Flażek, radio, przełącznik, segmentowany wybór i pole wyszukiwania — każdy stan to osobna komórka, w obu motywach. Kontrolki są w pełni interaktywne: prawdziwe najechanie myszą i Tab pokazują te same stany co wymuszone komórki „Najechanie” / „Fokus”.",
};

function Cell({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div className={["sc-controls__cell", className].filter(Boolean).join(" ")}>
      {children}
      <span className="sc-t-meta sc-controls__cell-label">{label}</span>
    </div>
  );
}

function GroupHeading({ title, onReplay }: { title: string; onReplay?: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--sc-s-3)", marginBottom: "var(--sc-s-3)" }}>
      <h3 className="sc-t-title-s sc-controls__group-title" style={{ margin: 0 }}>{title}</h3>
      {onReplay && (
        <button type="button" className="sc-controls__replay" onClick={onReplay}>
          Zagraj ponownie
        </button>
      )}
    </div>
  );
}

function CheckboxGroup() {
  const [checked, setChecked] = useState(true);
  function replay() {
    setChecked(false);
    window.setTimeout(() => setChecked(true), 60);
  }
  return (
    <div className="sc-controls__group">
      <GroupHeading title="Flażek" onReplay={replay} />
      <div className="sc-controls__matrix">
        <Cell label="Spoczynek">
          <Checkbox label="Powiadomienia e-mail" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Najechanie" className="sc-controls__force-hover">
          <Checkbox label="Powiadomienia e-mail" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Fokus" className="sc-controls__force-focus">
          <Checkbox label="Powiadomienia e-mail" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Zaznaczone (blik)">
          <Checkbox label="Powiadomienia e-mail" checked={checked} onChange={setChecked} />
        </Cell>
        <Cell label="Nieokreślone">
          <Checkbox label="Zaznacz wszystkie" checked={false} indeterminate onChange={() => undefined} />
        </Cell>
        <Cell label="Zablokowane">
          <Checkbox label="Powiadomienia e-mail" checked={false} disabled onChange={() => undefined} />
        </Cell>
        <Cell label="Zablokowane, zaznaczone">
          <Checkbox label="Powiadomienia e-mail" checked disabled onChange={() => undefined} />
        </Cell>
        <Cell label="Błąd">
          <Checkbox label="Wymagana zgoda na regulamin" checked={false} error onChange={() => undefined} />
        </Cell>
      </div>
    </div>
  );
}

function RadioSection({ theme }: { theme: string }) {
  const [value, setValue] = useState("dzien");
  return (
    <div className="sc-controls__group">
      <GroupHeading title="Radio" />
      <div className="sc-controls__matrix">
        <Cell label="Spoczynek">
          <Radio label="Dzień" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Najechanie" className="sc-controls__force-hover">
          <Radio label="Dzień" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Fokus" className="sc-controls__force-focus">
          <Radio label="Dzień" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Zaznaczone">
          <Radio label="Dzień" checked onChange={() => undefined} />
        </Cell>
        <Cell label="Zablokowane">
          <Radio label="Dzień" checked={false} disabled onChange={() => undefined} />
        </Cell>
        <Cell label="Błąd">
          <Radio label="Dzień" checked={false} error onChange={() => undefined} />
        </Cell>
      </div>
      <p className="sc-t-body-s sc-text-2" style={{ margin: "var(--sc-s-4) 0 var(--sc-s-3)" }}>
        Grupa — kropka przejeżdża między opcjami wspólnym <code className="sc-t-mono">layoutId</code>, nie gaśnie i zapala się.
      </p>
      <RadioGroup
        name={`motyw-${theme}`}
        legend="Motyw wyświetlania"
        value={value}
        onChange={setValue}
        options={[
          { value: "dzien", label: "Dzień" },
          { value: "noc", label: "Noc" },
          { value: "auto", label: "Automatycznie" },
        ]}
      />
    </div>
  );
}

function SwitchGroup() {
  const [checked, setChecked] = useState(true);
  return (
    <div className="sc-controls__group">
      <GroupHeading title="Przełącznik" />
      <div className="sc-controls__matrix">
        <Cell label="Wyłączony">
          <Switch label="Widoczność profilu" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Najechanie" className="sc-controls__force-hover">
          <Switch label="Widoczność profilu" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Fokus" className="sc-controls__force-focus">
          <Switch label="Widoczność profilu" checked={false} onChange={() => undefined} />
        </Cell>
        <Cell label="Włączony">
          <Switch label="Widoczność profilu" checked={checked} onChange={setChecked} />
        </Cell>
        <Cell label="Zablokowany">
          <Switch label="Widoczność profilu" checked={false} disabled onChange={() => undefined} />
        </Cell>
        <Cell label="Zablokowany, włączony">
          <Switch label="Widoczność profilu" checked disabled onChange={() => undefined} />
        </Cell>
        <Cell label="Błąd">
          <Switch label="Wymagana zgoda" checked={false} error onChange={() => undefined} />
        </Cell>
      </div>
    </div>
  );
}

function SegmentedSection({ theme }: { theme: string }) {
  const [value, setValue] = useState("kompakt");
  const options = [
    { value: "kompakt", label: "Kompaktowy" },
    { value: "rozwiniety", label: "Rozwinięty" },
  ];
  return (
    <div className="sc-controls__group">
      <GroupHeading title="Segmentowany przełącznik" />
      <div className="sc-controls__matrix">
        <Cell label="Spoczynek">
          <Segmented name={`widok-${theme}`} label="Widok listy" value={value} onChange={setValue} options={options} />
        </Cell>
        <Cell label="Naciśnięcie" className="sc-controls__force-press">
          <Segmented name={`widok-press-${theme}`} label="Widok listy" value="kompakt" onChange={() => undefined} options={options} />
        </Cell>
        <Cell label="Zablokowany">
          <Segmented name={`widok-disabled-${theme}`} label="Widok listy" value="kompakt" onChange={() => undefined} options={options} disabled />
        </Cell>
      </div>
    </div>
  );
}

function SearchFieldSection() {
  const [empty, setEmpty] = useState("");
  const [filled, setFilled] = useState("ustawa o mieszkalnictwie");
  return (
    <div className="sc-controls__group">
      <GroupHeading title="Pole wyszukiwania" />
      <div className="sc-controls__matrix">
        <Cell label="Puste (kliknij → fokus)">
          <SearchField value={empty} onChange={setEmpty} />
        </Cell>
        <Cell label="Z tekstem i licznikiem">
          <SearchField value={filled} onChange={setFilled} resultsCount={12} />
        </Cell>
        <Cell label="Błąd">
          <SearchField value="" onChange={() => undefined} error />
        </Cell>
        <Cell label="Zablokowane">
          <SearchField value="" onChange={() => undefined} disabled />
        </Cell>
      </div>
    </div>
  );
}

function ThemePanel({ theme }: { theme: "dark" | "light" }) {
  return (
    <div className="sc-root sc-controls__theme" data-sc-theme={theme}>
      <p className="sc-t-caption sc-controls__theme-label">{theme === "dark" ? "Noc" : "Dzień"}</p>
      <CheckboxGroup />
      <RadioSection theme={theme} />
      <SwitchGroup />
      <SegmentedSection theme={theme} />
      <SearchFieldSection />
    </div>
  );
}

export function Section() {
  return (
    <div>
      <ThemePanel theme="dark" />
      <ThemePanel theme="light" />
    </div>
  );
}
