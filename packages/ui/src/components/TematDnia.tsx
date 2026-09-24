"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import { getNewsFeed } from "../lib/portal";
import type { Article } from "../types";
import { Button, MorphIndicator, NewsCard } from "../kit";

type DailyTopic = {
  query: string | null;
  label: string | null;
  mode: "automatic" | "unavailable";
  source_count: number;
  article_count: number;
};

type Moment = { key: string; time: string; articles: Article[] };

function buildMoments(articles: Article[]): Moment[] {
  const buckets = new Map<string, Article[]>();
  for (const article of articles) {
    if (!article.published_date) continue;
    const hour = new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", hour: "2-digit", hour12: false })
      .format(new Date(article.published_date)).padStart(2, "0");
    const key = `${hour}:00`;
    buckets.set(key, [...(buckets.get(key) ?? []), article]);
  }
  return [...buckets.entries()].map(([key, items]) => ({ key, time: key, articles: items }));
}

export function TematDnia() {
  const topic = useQuery({
    queryKey: ["mvp-topic-of-day"],
    queryFn: () => apiFetch<DailyTopic>("/api/portal/topic-of-day/"),
    refetchInterval: 600_000,
    refetchIntervalInBackground: false,
    staleTime: 600_000,
  });
  const query = topic.data?.mode === "automatic" ? topic.data.query : null;
  const materials = useQuery({
    queryKey: ["mvp-topic-of-day-materials", query],
    queryFn: () => getNewsFeed({ query: query!, match: "words", pageSize: 40 }),
    enabled: Boolean(query),
  });
  const articles = materials.data?.results ?? [];
  const moments = useMemo(() => buildMoments(articles), [articles]);
  const [selected, setSelected] = useState(0);
  const activeIndex = Math.min(selected, Math.max(0, moments.length - 1));
  const selectedMoment = moments[activeIndex];

  if (!query || !articles.length) return null;

  return (
    <section className="sc-daily-topic" aria-label="Temat dnia">
      <header className="sc-daily-topic__head">
        <div>
          <p className="sc-daily-topic__eyebrow">TEMAT DNIA</p>
          <h2>{topic.data?.label ?? "Wspólny temat źródeł"}</h2>
          <p>{topic.data?.source_count ?? 0} źródeł · {topic.data?.article_count ?? articles.length} materiałów</p>
        </div>
      </header>
      <div className="sc-daily-topic__layout">
        <NewsCard article={articles[0]} size="large" headingLevel={3} showDescription />
        {moments.length > 1 ? <div className="sc-daily-topic__timeline" role="tablist" aria-label="Momenty na osi czasu">
          {moments.slice(0, 6).map((moment, index) => {
            const active = index === activeIndex;
            return <Button key={moment.key} type="button" variant="quiet" size="sm" pressed={active} role="tab" aria-selected={active} onClick={() => setSelected(index)} className="sc-daily-topic__moment">
              <MorphIndicator id="daily-topic-moment" active={active} variant="pill" />
              <span>{moment.time}</span><small>{moment.articles.length}</small>
            </Button>;
          })}
        </div> : null}
        {selectedMoment ? <section className="sc-daily-topic__materials" role="tabpanel" aria-label={`Materiały z ${selectedMoment.time}`}>
          <h3>Materiały z {selectedMoment.time}</h3>
          <div className="sc-daily-topic__cards">
            {selectedMoment.articles.slice(0, 4).map(article => <NewsCard key={article.id} article={article} size="compact" headingLevel={4} />)}
          </div>
        </section> : null}
      </div>
    </section>
  );
}
