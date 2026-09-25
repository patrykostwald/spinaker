"use client";

/**
 * Pas „Twój przegląd” (wzór: pas newslettera „Stay Updated”). Zamiast adresu e-mail — hasło,
 * z którego powstaje nitka użytkownika (zapis lokalny, jak dotąd). Wysłanie przewija do „Nitek użytkownika”
 * i otwiera tam formularz paska z wpisanym hasłem.
 */

import { useState, type FormEvent } from "react";
import { Button } from "../Button";
import { SearchField } from "../SearchField";

export function HomeBand({ onCreate }: { onCreate: (query: string) => void }) {
  const [query, setQuery] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(query.trim());
    setQuery("");
  }
  return (
    <section className="sc-home-band" aria-label="Twój przegląd">
      <div className="sc-home-band__copy">
        <h2 className="sc-t-title-m">Twój przegląd</h2>
        <p className="sc-t-body-s sc-text-2">Wpisz hasło, nazwisko lub temat — zbudujemy z niego własną nitkę materiałów. Zapis na tym urządzeniu.</p>
      </div>
      <form className="sc-home-band__form" onSubmit={submit}>
        <SearchField value={query} onChange={setQuery} placeholder="Hasło lub nazwisko" label="Hasło własnego paska" />
        <Button type="submit" variant="primary" size="md">
          Dodaj pasek
        </Button>
      </form>
    </section>
  );
}
