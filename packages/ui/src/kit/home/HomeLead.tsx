"use client";

/**
 * Wiadomości dnia — podsumowanie jednego, bieżącego dnia (nie jeden wybrany temat): jeden wspólny
 * pas, po lewej największy box (najnowsze doniesienie dnia z wiodących źródeł), po prawej oś
 * kolejnych doniesień tego dnia (`mini`, przewijana w pionie w obrębie pasa; na telefonie lista).
 * Dane: `/api/feed/?mode=top` — dzisiejsze materiały z redakcyjnego wyboru dziesięciu źródeł.
 * Gdy dziś jeszcze nic nie ma — najnowsze materiały, a nagłówek mówi to wprost.
 * (Osobny, redakcyjny „Temat dnia” w lustrzanym układzie — oś po lewej, box po prawej — jest planowany.)
 */

import { motion } from "framer-motion";
import { Button } from "../Button";
import { NewsCard } from "../NewsCard";
import { useMotionTokens } from "../motion/useMotionTokens";
import type { Article } from "../../types";

export function HomeLead({
  main,
  related,
  fallback,
  dateLabel,
  href,
}: {
  main: Article | null;
  related: Article[];
  /** `true` — dziś brak doniesień z wiodących źródeł, pas pokazuje najnowsze materiały. */
  fallback: boolean;
  /** Np. „piątek, 25 września” — pusty do hydratacji (data liczona po stronie klienta). */
  dateLabel: string;
  href: string;
}) {
  const m = useMotionTokens();
  return (
    <section className="sc-home-section sc-home-lead" aria-label="Wiadomości dnia">
      <div className="sc-home-band-surface">
        <header className="sc-home-section__head sc-home-lead__head">
          <div>
            <p className="sc-t-caption sc-text-3 sc-home-kicker" suppressHydrationWarning>
              {dateLabel ? `Podsumowanie dnia · ${dateLabel}` : "Podsumowanie dnia"}
            </p>
            <h2 className="sc-t-title-l sc-home-section__title">Wiadomości dnia</h2>
          </div>
          <div className="sc-home-section__actions">
            <p className="sc-t-body-s sc-text-2">{fallback ? "Dziś jeszcze bez doniesień z wiodących źródeł — najnowsze materiały" : "Najważniejsze doniesienia dnia z wiodących źródeł"}</p>
            <Button href={href} variant="quiet" size="sm">
              Zobacz wszystko
            </Button>
          </div>
        </header>

        <div className="sc-home-lead__grid">
          <div className="sc-home-lead__main">
            {main ? (
              <NewsCard article={main} size="large" headingLevel={3} eyebrow={fallback ? "Najnowszy materiał" : "Wiadomość dnia"} priority />
            ) : (
              <div className="sc-home-anchor-placeholder sc-home-lead__placeholder">
                <div className="sc-skeleton sc-home-anchor-placeholder__media" />
                <span className="sc-t-caption sc-text-3">Wiadomości dnia</span>
                <strong className="sc-t-title-m">Ładuję dzisiejsze doniesienia…</strong>
              </div>
            )}
          </div>

          <div className="sc-home-lead__side">
            <ol className="sc-home-lead__list" role="list" aria-label={fallback ? "Najnowsze materiały" : "Kolejne doniesienia dnia"} tabIndex={0}>
              {related.length
                ? related.map((article, index) => (
                    <motion.li key={article.id} initial={{ opacity: 0, y: m.rise }} animate={{ opacity: 1, y: 0 }} transition={m.t("ui", { delay: Math.min(index, 6) * m.stagger })}>
                      <NewsCard article={article} size="mini" headingLevel={4} expandable={false} />
                    </motion.li>
                  ))
                : [0, 1, 2, 3].map((i) => (
                    <li key={i} aria-hidden="true">
                      <span className="sc-skeleton sc-home-lead__skeleton" />
                    </li>
                  ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
