"use client";

/**
 * Hero (wzór: duży materiał + panel „wyniki” po prawej). Po lewej materiał kotwiczący Tematu dnia
 * (`large`, tekst nad zdjęciem); po prawej panel z osią czasu tematu — godzina · źródło · tytuł;
 * każdy wiersz otwiera materiał w portalu. Bez tematu dnia: najnowszy materiał + lista najnowszych.
 * Pod heroem (gdy temat jest) — „Nitka tematu”: taśma materiałów od najstarszej publikacji.
 */

import { motion } from "framer-motion";
import { Button } from "../Button";
import { NewsCard } from "../NewsCard";
import { useMotionTokens } from "../motion/useMotionTokens";
import { usePortalApi } from "../portal/PortalProvider";
import { categoryLabel, formatTimePl } from "../../lib/utils";
import type { Article } from "../../types";
import { Strip } from "./Strip";

export type LeadRow = { article: Article; time: string };

function PanelRow({ row }: { row: LeadRow }) {
  const m = useMotionTokens();
  const portal = usePortalApi();
  return (
    <li>
      <motion.button
        type="button"
        className="sc-home-lead__row sc-hoverable"
        onClick={(event) => portal.open(row.article, event.currentTarget)}
        whileTap={{ scale: m.scale(0.98), transition: m.t("press") }}
        data-material-id={row.article.id}
      >
        <span className="sc-home-lead__row-time sc-t-meta">{row.time}</span>
        <span className="sc-home-lead__row-body">
          <span className="sc-t-caption sc-text-3">
            {row.article.source.name} · {categoryLabel(row.article.category)}
          </span>
          <span className="sc-t-title-xs sc-home-lead__row-title">{row.article.title}</span>
        </span>
      </motion.button>
    </li>
  );
}

export function HomeLead({
  main,
  eyebrow,
  panelTitle,
  rows,
  panelHref,
  thread,
}: {
  main: Article | null;
  eyebrow: string;
  panelTitle: string;
  rows: LeadRow[];
  panelHref: string;
  thread?: Article[];
}) {
  return (
    <section className="sc-home-lead" aria-label="Materiał dnia">
      <div className="sc-home-lead__grid">
        <div className="sc-home-lead__main">
          {main ? (
            <NewsCard article={main} size="large" headingLevel={2} eyebrow={eyebrow} priority />
          ) : (
            <div className="sc-home-anchor-placeholder sc-home-lead__placeholder">
              <div className="sc-skeleton sc-home-anchor-placeholder__media" />
              <span className="sc-t-caption sc-text-3">{eyebrow}</span>
              <strong className="sc-t-title-m">Materiał dnia pojawi się, gdy źródła opiszą wspólne wydarzenie.</strong>
            </div>
          )}
        </div>
        <aside className="sc-home-lead__panel" aria-label={panelTitle}>
          <header className="sc-home-lead__panel-head">
            <h2 className="sc-t-title-s">{panelTitle}</h2>
            <Button href={panelHref} variant="quiet" size="sm">
              Zobacz wszystko
            </Button>
          </header>
          {rows.length ? (
            <ol className="sc-home-lead__rows" role="list">
              {rows.map((row) => (
                <PanelRow key={row.article.id} row={row} />
              ))}
            </ol>
          ) : (
            <ol className="sc-home-lead__rows" aria-hidden="true">
              {[0, 1, 2, 3, 4].map((i) => (
                <li key={i} className="sc-home-lead__row sc-home-lead__row--skeleton">
                  <span className="sc-t-meta sc-text-3">XX:XX</span>
                  <span className="sc-skeleton sc-home-lead__row-skeleton" />
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>

      {thread && thread.length > 0 ? (
        <div className="sc-home-lead__thread">
          <header className="sc-home-subhead">
            <span className="sc-t-caption sc-text-3">Nitka tematu</span>
            <p className="sc-t-body-s sc-text-2">Materiały powiązane wspólnym hasłem, ułożone według czasu publikacji.</p>
          </header>
          <Strip label="Nitka tematu dnia">
            {thread.map((article) => (
              <div key={article.id} className="sc-strip__slot">
                <NewsCard article={article} size="compact" headingLevel={3} />
              </div>
            ))}
          </Strip>
        </div>
      ) : null}
    </section>
  );
}

/** Godzina publikacji do panelu — `--:--` gdy daty nie ma. */
export function rowTime(article: Article): string {
  const iso = article.published_date;
  return iso && iso !== "undated" && iso !== "unknown" ? formatTimePl(iso) : "--:--";
}
