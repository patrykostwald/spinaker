"use client";

import { useOwnerId } from "../lib/personal";
import type { Article } from "../types";
import { NewsCard } from "../kit";
import { ArticleFavoriteButton } from "./ArticleFavoriteButton";

export function MaterialBox({ article }: { article: Article }) {
  const { ownerId } = useOwnerId();
  return <NewsCard article={article} size="medium" action={ownerId ? <ArticleFavoriteButton articleId={article.id} title={article.title} compact /> : undefined} />;
}
