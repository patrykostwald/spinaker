"use client";

/**
 * Nitki użytkownika (dawny „Twój przegląd” z Bazy, w miejscu mozaiki „Wszystkie źródła”):
 * pasek konfiguracji (wyśrodkowany: hasło · kategoria · źródło + „+ Dodaj pasek”), a pod nim
 * do {@link MAX_PERSONAL_STRIPS} własnych nitek — każda to filtr hasło/kategoria/źródło nad
 * `/api/portal/news`, zapis lokalny, kolejność przeciągana za uchwyt (`ReorderableStrips`).
 * Limit pilnuje interfejs (przycisk i pigułki wyłączone, formularz się nie otwiera, zapis
 * odrzucany) oraz `savePersonalStrip`.
 */

import { forwardRef, useEffect, useMemo, useState, type FormEvent } from "react";
import { Button } from "../Button";
import { Dropdown } from "../Dropdown";
import { NewsCard } from "../NewsCard";
import { ReorderableStrips } from "../ReorderableStrips";
import { SearchField } from "../SearchField";
import type { CategoryOption } from "../../lib/portal";
import {
  MAX_PERSONAL_STRIPS,
  loadPersonalStrips,
  removePersonalStrip,
  savePersonalStrip,
  updatePersonalStrip,
  type PersonalStrip,
} from "../../lib/personalStrips";
import type { Source } from "../../types";
import { useHomeFeed } from "./data";
import { Strip } from "./Strip";

function StripForm({
  initial,
  categories,
  sources,
  onSave,
  onCancel,
}: {
  initial?: PersonalStrip;
  categories: CategoryOption[];
  sources: Source[];
  onSave: (strip: PersonalStrip) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState(initial?.query ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [sourceId, setSourceId] = useState<string>(initial?.sourceId ? String(initial.sourceId) : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = sources.find((item) => String(item.id) === sourceId);
    const label = query.trim() || categories.find((item) => item.value === category)?.label || source?.name || "Moja nitka";
    onSave({ id: initial?.id || `${Date.now()}`, label, query: query.trim(), category, sourceId: sourceId ? Number(sourceId) : "" });
  }

  return (
    <form className="sc-home-stripform" onSubmit={submit}>
      <p className="sc-t-caption sc-text-3">{initial?.id ? "Edytuj nitkę" : "Nowa nitka"}</p>
      <div className="sc-home-stripform__row">
        <SearchField value={query} onChange={setQuery} placeholder="Hasło lub nazwisko" label="Hasło lub nazwisko" />
        <Dropdown
          label={categories.find((item) => item.value === category)?.label ?? "Kategoria: wszystkie"}
          ariaLabel="Kategoria"
          mode="single"
          presentation="auto"
          items={[{ value: "", label: "Wszystkie" }, ...categories]}
          value={category}
          onChange={(value) => setCategory(value as string)}
        />
        <Dropdown
          label={sources.find((item) => String(item.id) === sourceId)?.name ?? "Źródło: wszystkie"}
          ariaLabel="Źródło"
          mode="single"
          presentation="auto"
          items={[{ value: "", label: "Wszystkie" }, ...sources.map((item) => ({ value: String(item.id), label: item.name }))]}
          value={sourceId}
          onChange={(value) => setSourceId(value as string)}
        />
        <div className="sc-home-stripform__actions">
          <Button type="submit" variant="primary" size="sm">
            Pokaż materiały
          </Button>
          <Button type="button" variant="quiet" size="sm" onClick={onCancel}>
            Anuluj
          </Button>
        </div>
      </div>
    </form>
  );
}

function PersonalStripBody({ strip, onEdit, onRemove }: { strip: PersonalStrip; onEdit: () => void; onRemove: () => void }) {
  const feed = useHomeFeed(`personal-${strip.id}`, {
    query: strip.query,
    categories: strip.category ? [strip.category] : [],
    sources: strip.sourceId ? [strip.sourceId] : [],
    pageSize: 20,
  });
  const articles = feed.data?.results ?? [];
  return (
    <div className="sc-home-personal__strip">
      <div className="sc-home-personal__actions">
        <Button variant="quiet" size="sm" onClick={onEdit}>
          Edytuj
        </Button>
        <Button variant="quiet" size="sm" onClick={onRemove}>
          Usuń pasek
        </Button>
      </div>
      {feed.isPending ? <p role="status" className="sc-t-body-s sc-text-2">Ładuję materiały…</p> : null}
      {feed.isSuccess && !articles.length ? <p className="sc-t-body-s sc-text-2">Nie znaleźliśmy jeszcze materiałów pasujących do tego wyboru.</p> : null}
      {articles.length > 0 ? (
        <Strip label={strip.label}>
          {articles.map((article) => (
            <div key={article.id} className="sc-strip__slot">
              <NewsCard article={article} size="compact" headingLevel={4} />
            </div>
          ))}
        </Strip>
      ) : null}
    </div>
  );
}

export type StripDraft = { query: string; nonce: number };

export const HomeThreads = forwardRef<HTMLElement, { categories: CategoryOption[]; sources: Source[]; draft: StripDraft | null }>(function HomeThreads(
  { categories, sources, draft },
  ref,
) {
  const [strips, setStrips] = useState<PersonalStrip[]>([]);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    setStrips(loadPersonalStrips());
  }, []);

  const atLimit = strips.length >= MAX_PERSONAL_STRIPS;

  // Pas „Twój przegląd” na dole strony: otwiera formularz z wpisanym hasłem (nonce — każde wysłanie),
  // ale nie ponad limit — wtedy pasek konfiguracji pokazuje komunikat o limicie.
  useEffect(() => {
    if (!draft || loadPersonalStrips().length >= MAX_PERSONAL_STRIPS) return;
    setAdding(true);
    setEditingId(null);
  }, [draft]);

  function startAdding() {
    if (atLimit) return;
    setAdding(true);
    setEditingId(null);
  }

  function saveNew(strip: PersonalStrip) {
    if (loadPersonalStrips().length >= MAX_PERSONAL_STRIPS) {
      setStrips(loadPersonalStrips());
      setAdding(false);
      return;
    }
    setStrips(savePersonalStrip({ ...strip, id: strip.id || `${Date.now()}` }));
    setAdding(false);
  }

  const rows = useMemo(() => strips.map((strip) => ({ id: strip.id, title: strip.label, strip })), [strips]);

  return (
    <section ref={ref} id="nitki" className="sc-home-section sc-home-threads" aria-label="Nitki użytkownika">
      <header className="sc-home-section__head">
        <h2 className="sc-t-title-l sc-home-section__title">Nitki użytkownika</h2>
        <p className="sc-t-meta sc-text-2" aria-live="polite">
          {strips.length} / {MAX_PERSONAL_STRIPS}
        </p>
      </header>

      <div className="sc-home-threads__config">
        {adding && !atLimit ? (
          <StripForm
            key={draft?.nonce ?? "new"}
            initial={draft?.query ? { id: "", label: "", query: draft.query, category: "", sourceId: "" } : undefined}
            categories={categories}
            sources={sources}
            onSave={saveNew}
            onCancel={() => setAdding(false)}
          />
        ) : (
          <div className="sc-home-threads__bar">
            <p className="sc-t-body-s sc-text-2">
              {atLimit ? `Masz już ${MAX_PERSONAL_STRIPS} nitek — usuń jedną, aby dodać kolejną.` : "Dopasuj własny pasek: hasło, kategoria lub źródło."}
            </p>
            <div className="sc-home-pills">
              {["Hasło", "Kategoria", "Źródło"].map((label) => (
                <Button key={label} variant="quiet" shape="pill" size="sm" disabled={atLimit} onClick={startAdding}>
                  {label}
                </Button>
              ))}
              <Button variant="secondary" size="sm" disabled={atLimit} onClick={startAdding}>
                + Dodaj pasek
              </Button>
            </div>
          </div>
        )}
      </div>

      {rows.length > 0 ? (
        <ReorderableStrips
          strips={rows}
          storageKey="spinclinic-home-strips-order"
          label="Kolejność Twoich nitek"
          renderStrip={(row) =>
            editingId === row.id ? (
              <StripForm
                initial={row.strip}
                categories={categories}
                sources={sources}
                onSave={(strip) => { setStrips(updatePersonalStrip(strip)); setEditingId(null); }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <PersonalStripBody
                strip={row.strip}
                onEdit={() => { setEditingId(row.id); setAdding(false); }}
                onRemove={() => { setStrips(removePersonalStrip(row.id)); if (editingId === row.id) setEditingId(null); }}
              />
            )
          }
        />
      ) : null}
    </section>
  );
});
