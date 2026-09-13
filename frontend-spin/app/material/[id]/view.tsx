"use client";
import { useState } from 'react';
import Link from 'next/link';
import { ArticleCard, ArticleModal, type Article } from '@spin-clinic/ui';

export default function MaterialView({ article }: { article: Article }) {
  const [open, setOpen] = useState(true);
  return <article className="mx-auto max-w-4xl space-y-5">
    <Link href="/" className="text-sm text-primary">← Przeglądaj media</Link>
    <h1 className="text-xl font-semibold">{article.title}</h1>
    <p className="text-sm text-slate-500">{article.source.name} · Materiał źródłowy i jego kontekst</p>
    <div className="max-w-sm"><ArticleCard article={article} onSelect={() => setOpen(true)} /></div>
    <ArticleModal article={open ? article : null} onClose={() => setOpen(false)} />
  </article>;
}
