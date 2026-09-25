"use client";

/**
 * Temat dnia — jeden wspólny pas: nagłówek, po lewej duży materiał kotwiczący (`large`), po prawej
 * pionowy pasek mniejszych materiałów powiązanych (`mini`, przewijany w pionie w obrębie pasa,
 * na telefonie zwykła lista pod kotwicą). Z tematem dnia — materiały tematu w kolejności publikacji;
 * bez tematu — najnowsze materiały (nagłówek mówi to wprost).
 */

import { motion } from "framer-motion";
import { Button } from "../Button";
import { NewsCard } from "../NewsCard";
import { useMotionTokens } from "../motion/useMotionTokens";
import type { Article } from "../../types";

export function HomeLead({
  main,
  label,
  related,
  href,
}: {
  main: Article | null;
  /** Nazwa tematu dnia; `null` — dziś bez wspólnego tematu (pas pokazuje najnowsze). */
  label: string | null;
  related: Article[];
  href: string;
}) {
  const m = useMotionTokens();
  return (
    <section className="sc-home-section sc-home-lead" aria-label="Temat dnia">
      <div className="sc-home-band-surface">
        <header className="sc-home-section__head sc-home-lead__head">
          <div>
            <p className="sc-t-caption sc-text-3 sc-home-kicker">Temat dnia</p>
            <h2 className="sc-t-title-l sc-home-section__title">{label ?? "Najnowsze materiały"}</h2>
          </div>
          <div className="sc-home-section__actions">
            <p className="sc-t-body-s sc-text-2">{label ? "Materiały tematu w kolejności publikacji" : "Dziś bez wspólnego tematu"}</p>
            <Button href={href} variant="quiet" size="sm">
              Zobacz wszystko
            </Button>
          </div>
        </header>

        <div className="sc-home-lead__grid">
          <div className="sc-home-lead__main">
            {main ? (
              <NewsCard article={main} size="large" headingLevel={3} eyebrow={label ? "Temat dnia" : "Najnowszy materiał"} priority />
            ) : (
              <div className="sc-home-anchor-placeholder sc-home-lead__placeholder">
                <div className="sc-skeleton sc-home-anchor-placeholder__media" />
                <span className="sc-t-caption sc-text-3">Temat dnia</span>
                <strong className="sc-t-title-m">Materiał dnia pojawi się, gdy źródła opiszą wspólne wydarzenie.</strong>
              </div>
            )}
          </div>

          <div className="sc-home-lead__side">
            <ol className="sc-home-lead__list" role="list" aria-label={label ? "Materiały powiązane z tematem dnia" : "Najnowsze materiały"} tabIndex={0}>
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
