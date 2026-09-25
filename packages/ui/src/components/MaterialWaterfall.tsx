"use client";

/**
 * „Wodospad” powiększonego boxa: baza powiązanych doniesień. Po otwarciu boxa przeszukujemy bazę
 * (`/api/articles/<id>/context/?page=N`, po 30 materiałów) i wyniki „spływają” z miniatury głównego
 * materiału do kolumn — ośmiu grup kategorii portalu (Artykuł, Film, Publiczne, Reklama…, alfabetycznie); każdy wiersz to inna data,
 * wiersze dochodzą w miarę zapełniania. Kilka pierwszych stron dociąga się samo, z krótką przerwą —
 * widać postęp szukania; dalej przycisk „Szukaj dalej”.
 */

import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button, NewsCard, useMotionTokens } from "../kit";
import type { ArticleContext as ArticleContextData } from "../lib/portal";
import { CATEGORY_GROUPS, categoryGroupOf } from "../lib/categoryGroups";
import { categoryLabel, formatDatePl } from "../lib/utils";
import type { Article } from "../types";
import { articleContextPage } from "./MaterialTimeline";

const AUTO_PAGES = 4;

type Found = { article: Article; date: string; order: number };

export function MaterialWaterfall({ article, onSelect }: { article: Article; onSelect?: (next: Article) => void }) {
  const client = useQueryClient();
  const m = useMotionTokens();
  const [pages, setPages] = useState<ArticleContextData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const loadingRef = useRef(false);
  const articleRef = useRef(article.id);

  async function loadPage(page: number) {
    if (loadingRef.current) return;
    const id = article.id;
    loadingRef.current = true;
    setLoading(true);
    setError("");
    try {
      const data = await client.fetchQuery(articleContextPage(id, page));
      // Odpowiedź dla poprzednio otwartego boxa nie może trafić do wyników nowego.
      if (articleRef.current !== id) return;
      setPages((current) => (current.length === page - 1 ? [...current, data] : current));
    } catch {
      if (articleRef.current === id) setError("Nie udało się przeszukać bazy.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }

  // Nowy box — od zera; pierwsza strona od razu, kolejne same (do AUTO_PAGES) z przerwą.
  useEffect(() => {
    articleRef.current = article.id;
    setPages([]);
    loadingRef.current = false;
    void loadPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tylko zmiana materiału restartuje szukanie
  }, [article.id]);

  const last = pages[pages.length - 1];
  const nextPage = last?.next_page ?? null;
  useEffect(() => {
    if (!nextPage || pages.length >= AUTO_PAGES || loading || error) return;
    const timer = window.setTimeout(() => void loadPage(nextPage), 650);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadPage czyta aktualny stan przez ref
  }, [nextPage, pages.length, loading, error]);

  const summary = pages[0];
  const found = useMemo(() => {
    const out: Found[] = [];
    const seen = new Set<number>();
    pages.forEach((page) => {
      for (const [date, items] of Object.entries(page.timeline)) {
        for (const item of items) {
          if (seen.has(item.id) || item.id === article.id) continue;
          seen.add(item.id);
          out.push({ article: item, date, order: out.length });
        }
      }
    });
    return out;
  }, [pages, article.id]);

  // Kolumny: grupy kategorii portalu (alfabetycznie), tylko te, w których są wyniki (także z liczników kontekstu).
  const columns = useMemo(() => {
    const present = new Set(found.map((item) => categoryGroupOf(item.article.category).key));
    for (const item of summary?.counts ?? []) if (item.count > 0) present.add(categoryGroupOf(item.category).key);
    return CATEGORY_GROUPS.filter((group) => present.has(group.key)).map((group) => ({ key: group.key, label: group.label }));
  }, [summary, found]);

  const columnOf = (category: string) => categoryGroupOf(category).key;
  const dates = useMemo(() => {
    const keys = [...new Set(found.map((item) => item.date))];
    return keys.sort((a, b) => (a === "unknown" ? 1 : b === "unknown" ? -1 : b.localeCompare(a)));
  }, [found]);

  const complete = Boolean(summary) && !nextPage;
  const total = summary?.total ?? 0;
  const src = article.image_url?.trim();

  return (
    <section className="sc-material-waterfall" aria-label="Baza powiązanych doniesień">
      <header className="sc-material-waterfall__head">
        <div className="sc-material-waterfall__source" aria-hidden="true">
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element -- miniatura źródła wodospadu, jak w powierzchni materiału
            <img src={src} alt="" />
          ) : (
            <span className="sc-material-waterfall__source-empty sc-t-caption">{categoryLabel(article.category)}</span>
          )}
        </div>
        <div>
          <p className="sc-t-caption sc-text-3">Baza powiązanych doniesień</p>
          <h3 className="sc-t-title-s">Kategorie × daty</h3>
          <p className="sc-t-meta sc-text-2" role="status" aria-live="polite">
            {!summary
              ? "Przeszukuję bazę…"
              : `${found.length} z ${total} powiązanych${complete ? " · wszystkie" : loading ? " · szukam dalej…" : ""}${summary.keywords.length ? ` · po słowach: ${summary.keywords.slice(0, 4).join(", ")}` : ""}`}
          </p>
        </div>
      </header>

      {error ? (
        <p role="alert" className="sc-t-body-s sc-text-2">
          {error}{" "}
          <button type="button" className="sc-home-linkbtn" onClick={() => void loadPage(pages.length + 1)}>
            Ponów
          </button>
        </p>
      ) : null}
      {summary && !found.length && complete ? <p className="sc-t-body-s sc-text-2">W bazie nie ma jeszcze materiałów powiązanych z tym boxem.</p> : null}

      {found.length ? (
        <div className="sc-material-waterfall__scroll" tabIndex={0} aria-label="Kolumny kategorii — przewijaj">
          <div className="sc-material-waterfall__grid" style={{ ["--sc-wf-cols" as string]: columns.length }}>
            {columns.map((column) => (
              <p key={column.key} className="sc-material-waterfall__col-head sc-t-caption">
                {column.label}
                <span className="sc-text-3"> · {found.filter((item) => columnOf(item.article.category) === column.key).length}</span>
              </p>
            ))}
            {dates.map((date) => (
              <div key={date} className="sc-material-waterfall__row" role="group" aria-label={date === "unknown" ? "Data nieustalona" : formatDatePl(date)}>
                <p className="sc-material-waterfall__date sc-t-meta">{date === "unknown" ? "Data nieustalona" : formatDatePl(date)}</p>
                {columns.map((column) => (
                  <div key={column.key} className="sc-material-waterfall__cell">
                    {found
                      .filter((item) => item.date === date && columnOf(item.article.category) === column.key)
                      .map((item) => (
                        <motion.div
                          key={item.article.id}
                          initial={{ opacity: 0, y: m.reduced ? 0 : -72, scale: m.reduced ? 1 : 0.92 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          transition={m.t("ui", { delay: m.reduced ? 0 : Math.min(item.order % 30, 14) * 0.045 })}
                        >
                          <NewsCard article={item.article} size="mini" headingLevel={4} expandable={false} onOpen={onSelect} />
                        </motion.div>
                      ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {summary && nextPage && pages.length >= AUTO_PAGES ? (
        <div className="sc-material-waterfall__more">
          <Button variant="secondary" size="sm" loading={loading} onClick={() => void loadPage(nextPage)}>
            Szukaj dalej
          </Button>
        </div>
      ) : null}
    </section>
  );
}
