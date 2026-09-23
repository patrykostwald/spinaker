"use client";

import Image from "next/image";
import Link from "next/link";
import { categoryLabel, formatShortDatePl, formatTimePl, materialTypeLabel } from "../lib/utils";
import type { Article } from "../types";

export function MaterialBox({ article }: { article: Article }) {
  return (
    <Link href={`/material/${article.id}`} className="material-box">
      <span className="material-box-meta">
        <span className="material-box-source">{article.source.name} · {categoryLabel(article.category)}</span>
        <span className="material-box-time">
          <span className="material-box-hour">{formatTimePl(article.published_date)}</span>
          <span className="material-box-date">{formatShortDatePl(article.published_date)}</span>
        </span>
      </span>
      <span className="material-box-media">
        {article.image_url ? (
          <Image unoptimized src={article.image_url} alt="" fill sizes="120px" className="material-box-image" />
        ) : (
          <span className="material-box-type" aria-hidden="true">{materialTypeLabel(article.category)}</span>
        )}
      </span>
      <span className="material-box-title">{article.title}</span>
    </Link>
  );
}

export function EmptyMaterialSlot({ index, label }: { index: number; label?: string }) {
  return (
    <div className="material-box material-box-empty" role="img" aria-label={label ? `${label} — przykładowy pusty box` : `Slot ${index} — brak materiału`}>
      <span className={label ? "material-box-empty-label" : "material-box-empty-rank"}>{label ?? String(index).padStart(2, '0')}</span>
    </div>
  );
}
