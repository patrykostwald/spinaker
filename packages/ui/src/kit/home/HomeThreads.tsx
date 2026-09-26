"use client";

/**
 * Nitki użytkownika — do pięciu własnych pasków „Twoje wiadomości”:
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
import { CATEGORY_GROUPS, categoryGroupByKey, categoryGroupOf, expandCategories } from "../../lib/categoryGroups";
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
  sources,
  onSave,
  onCancel,
}: {
  initial?: PersonalStrip;
  sources: Source[];
  onSave: (strip: PersonalStrip) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState(initial?.query ?? "");
  // Starsze nitki mogą mieć zapisaną pojedynczą kategorię backendu — pokazujemy jej grupę.
  const [category, setCategory] = useState(initial?.category ? (categoryGroupByKey(initial.category)?.key ?? categoryGroupOf(initial.category).key) : "");
  const [sourceId, setSourceId] = useState<string>(initial?.sourceId ? String(initial.sourceId) : "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = sources.find((item) => String(item.id) === sourceId);
    const label = query.trim() || categoryGroupByKey(category)?.label || source?.name || "Moja nitka";
    onSave({ id: initial?.id || `${Date.now()}`, label, query: query.trim(), category, sourceId: sourceId ? Number(sourceId) : "" });
  }

  return (
    <form className="sc-home-stripform" onSubmit={submit}>
      <p className="sc-t-caption sc-text-3">{initial?.id ? "Edytuj nitkę" : "Nowa nitka"}</p>
      <div className="sc-home-stripform__row">
        <SearchField value={query} onChange={setQuery} placeholder="Hasło lub nazwisko" label="Hasło lub nazwisko" />
        <Dropdown
          label={categoryGroupByKey(category)?.label ?? "Kategoria: wszystkie"}
          ariaLabel="Kategoria"
          mode="single"
          presentation="auto"
          items={[{ value: "", label: "Wszystkie" }, ...CATEGORY_GROUPS.map((group) => ({ value: group.key, label: group.label }))]}
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
    categories: strip.category ? expandCategories([strip.category]) : [],
    sources: strip.sourceId ? [strip.sourceId] : [],
    pageSize: 20,
  });
  const articles = feed.data?.results ?? [];
  return (
    <div className="sc-home-personal__strip">
      <div className="sc-home-personal__actions">
        <button type="button" onClick={onEdit}>Edytuj</button>
        <span aria-hidden="true">|</span>
        <button type="button" onClick={onRemove} aria-label={`Usuń pasek: ${strip.label}`}>Usuń</button>
      </div>
      {feed.isPending ? <p role="status" className="sc-t-body-s sc-text-2">Ładuję materiały…</p> : null}
      {feed.isSuccess && !articles.length ? <p className="sc-t-body-s sc-text-2">Nie znaleźliśmy jeszcze materiałów pasujących do tego wyboru.</p> : null}
      {articles.length > 0 ? (
        <Strip label={strip.label}>
          {articles.map((article) => (
            <div key={article.id} className="sc-strip__slot">
              <NewsCard article={article} size="compact" headingLevel={4} expandable={false} />
            </div>
          ))}
        </Strip>
      ) : null}
    </div>
  );
}

export const HomeThreads = forwardRef<HTMLElement, { sources: Source[] }>(function HomeThreads(
  { sources },
  ref,
) {
  const [strips, setStrips] = useState<PersonalStrip[]>([]);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    setStrips(loadPersonalStrips());
  }, []);

  const atLimit = strips.length >= MAX_PERSONAL_STRIPS;

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
    <section ref={ref} id="nitki" className="sc-home-section sc-home-threads" aria-label="Twoje wiadomości">
      <header className="sc-home-section__head">
        <h2 className="sc-t-title-l sc-home-section__title">Twoje wiadomości</h2>
        <p className="sc-t-meta sc-text-2" aria-live="polite">
          {strips.length} / {MAX_PERSONAL_STRIPS}
        </p>
      </header>

      <div className="sc-home-threads__config">
        {adding && !atLimit ? (
          <StripForm
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
