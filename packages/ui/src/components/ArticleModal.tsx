"use client";
import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';
import { categoryLabel, formatDateTimePl } from '../lib/utils';
import type { Article } from '../types';
import { Dialog } from './Dialog';
import { VotingDetails } from './VotingDetails';
import { ArticleContext } from './ArticleContext';
import { ArticleOpinions } from './ArticleOpinions';
export function ArticleModal({ article, onClose }: { article: Article | null; onClose: () => void }) {
  return <Dialog open={Boolean(article)} onClose={onClose} title="Materiał i kontekst" className="article-dialog">
    {article && <ArticleDetails key={article.id} initialArticle={article} />}
  </Dialog>;
}

function ArticleDetails({ initialArticle }: { initialArticle: Article }) {
  const [article, setArticle] = useState(initialArticle);
  const container = useRef<HTMLDivElement>(null);
  function navigate(next: Article) {
    setArticle(next);
    container.current?.closest('dialog')?.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  return <div ref={container}>
    {article.id !== initialArticle.id && <button className="context-back" onClick={() => navigate(initialArticle)}>← Wróć do wybranego materiału</button>}
    <motion.div key={article.id} className="article-source-detail" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {article.image_url && <div className="relative h-64 bg-slate-100"><Image unoptimized src={article.image_url} alt="" fill sizes="640px" className="object-cover" /></div>}
      <div className="space-y-5 p-6">
        <span className="source-category-label" data-category={article.category}>{categoryLabel(article.category)}</span>
        <h2 className="text-2xl font-bold">{article.title}</h2>
        <p className="text-sm text-slate-500">{article.source.name} · {formatDateTimePl(article.published_date, article.date_precision)}{article.author ? ` · ${article.author}` : ''}</p>
        <p className="text-sm text-slate-500">{article.official ? `${article.official.date_label}: ${formatDateTimePl(article.published_date, article.date_precision)}. Metadane z urzędowego rejestru.` : article.category_reviewed ? 'Kategoria sprawdzona przez redakcję' : 'Kategoria wstępna — wymaga przeglądu'}</p>
        {!article.published_date && article.discovered_at && <p className="text-sm text-slate-500">Wykryto przez agregator: {formatDateTimePl(article.discovered_at)}. To nie jest data publikacji.</p>}
        {article.evidence_note && <div className="rounded-lg border-l-4 border-primary bg-slate-50 p-4"><h3 className="font-bold">Uwagi redakcji o źródle</h3><p>{article.evidence_note}</p></div>}
        {!article.official && <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{article.content_status === 'extracted_text' ? 'Wyszukiwanie obejmuje również tekst udostępniony przez wydawcę. Nie potwierdzamy kompletności artykułu.' : article.content_status === 'metadata_only' ? 'Pobraliśmy metadane. Tekst artykułu nie jest dostępny w naszej bazie — otwórz źródło.' : 'Tekstu artykułu jeszcze nie pobrano. W bazie są dostępne metadane i odnośnik.'}</p>}
        {article.description && <p className="whitespace-pre-line leading-relaxed text-slate-700">{article.description}</p>}
        {article.voting && <VotingDetails key={article.id} article={article} />}
        {article.official && <section className="space-y-2 rounded-lg bg-slate-50 p-4 text-sm"><h3 className="font-bold">Rekord urzędowy</h3>{article.official.status && <p>Status w rejestrze: {article.official.status}</p>}<p>Pobrano: {formatDateTimePl(article.official.fetched_at)}</p>{article.official.attachments.map(a => <a key={a.url} href={a.url} target="_blank" rel="noopener noreferrer" className="block text-primary underline">Załącznik: {a.name} ↗</a>)}</section>}
        {Boolean(article.evidence_links?.length) && <section><h3 className="font-bold">Dlaczego ten materiał pasuje do tematu?</h3>{article.evidence_links?.map(link => <div key={link.source_url + link.phrase} className="mt-3 text-sm"><p>{link.explanation}</p><a href={link.source_url} target="_blank" rel="noopener noreferrer" className="text-primary underline">Źródło powiązania: {link.phrase} ↗</a></div>)}</section>}
        <a href={article.url} target="_blank" rel="noopener noreferrer" className="inline-flex rounded-lg bg-primary px-6 py-3 font-semibold text-white">Otwórz źródło →</a>
      </div>
    </motion.div>
    <ArticleContext key={`context-${article.id}`} article={article} onSelect={navigate}>
      <ArticleOpinions key={`opinions-${article.id}`} article={article} />
    </ArticleContext>
  </div>;
}
