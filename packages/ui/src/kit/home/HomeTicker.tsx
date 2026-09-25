"use client";

/**
 * Pasek newsowy spin.clinic („Top 10”) — pozioma taśma najnowszych materiałów, przewijana
 * w prawo/lewo (palcem, kółkiem, strzałkami) na każdej szerokości, także na telefonie.
 * Zawężają go filtry z wiersza nad nim (grupa źródeł · temat · hasło). Podpis pod taśmą
 * przedstawia ideę pasków: użytkownik może ustawić do pięciu własnych w „Nitkach użytkownika”.
 */

import { NewsCard } from "../NewsCard";
import type { Article } from "../../types";
import { EmptySlot, Strip } from "./Strip";

const SLOTS = 10;

export function HomeTicker({ articles, loading = false }: { articles: Article[]; loading?: boolean }) {
  const items = articles.slice(0, SLOTS);
  return (
    <section className="sc-home-ticker" aria-label="Pasek newsowy spin.clinic">
      <Strip label="Pasek newsowy spin.clinic" slot="300px">
        {items.length
          ? items.map((article) => (
              <div key={article.id} className="sc-strip__slot">
                <NewsCard article={article} size="mini" headingLevel={3} />
              </div>
            ))
          : Array.from({ length: loading ? 4 : 1 }, (_, index) => (
              <div key={index} className="sc-strip__slot">
                <EmptySlot index={index + 1} label={loading ? "Ładuję…" : "Brak materiałów"} />
              </div>
            ))}
      </Strip>
      <p className="sc-t-body-s sc-text-2 sc-home-ticker__hint">
        To pasek newsowy spin.clinic. Możesz ustawić do pięciu własnych — po źródłach, kategorii lub haśle —{" "}
        <a href="#nitki" className="sc-home-linkbtn">
          w Nitkach użytkownika
        </a>
        .
      </p>
    </section>
  );
}
