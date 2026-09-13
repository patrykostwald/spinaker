'use client';
import { useEffect, useRef, useState } from 'react';
import { apiFetch, apiWrite } from './api';
import { readResearchStream } from './research-stream';
import type { Article, TimelineResponse } from '../types';

export type ResearchSource = { url: string; source_name: string; title?: string; status: string; published_date?: string | null };
export type ResearchSection = { text: string; citations: { start: number; end: number; url: string }[] };
export type ResearchResult = { archive_timeline: TimelineResponse['timeline']; limitation: string; sections: ResearchSection[]; sources: ResearchSource[] };
type State = {
  query: string; phase: 'checking' | 'searching' | 'completed' | 'disabled' | 'error' | 'stopped';
  message: string; sources: ResearchSource[]; articles: Article[]; result: ResearchResult | null; enriching: boolean;
};
const initial = (query: string): State => ({ query, phase: query ? 'checking' : 'disabled', message: '', sources: [], articles: [], result: null, enriching: false });

export function useLiveResearch(query: string) {
  const [state, setState] = useState<State>(() => initial(query));
  const [attempt, setAttempt] = useState(0);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    active.current = controller;
    setState(initial(query));
    if (!query.trim()) return () => controller.abort();
    let sources: ResearchSource[] = [];
    let terminal = false;
    let sawDone = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let deadlineTimer: ReturnType<typeof setTimeout> | undefined;
    let polling = false;
    const started = Date.now();
    const update = (change: Partial<State>) => { if (!controller.signal.aborted) setState(previous => ({ ...previous, ...change })); };
    const addSources = (incoming: ResearchSource[]) => {
      const byUrl = new Map(sources.map(source => [source.url, source]));
      incoming.forEach(source => byUrl.set(source.url, { ...byUrl.get(source.url), ...source }));
      sources = [...byUrl.values()].slice(0, 30);
      update({ sources });
    };
    const addArticles = (incoming: Article[]) => {
      if (controller.signal.aborted) return;
      setState(previous => ({ ...previous, articles: [...new Map([...previous.articles, ...incoming].map(article => [article.id, article])).values()] }));
    };
    async function refreshMetadata() {
      pollTimer = undefined;
      if (controller.signal.aborted || !sources.length || polling) return;
      if (Date.now() - started > 150_000) { update({ enriching: false }); return; }
      polling = true;
      let allStored = false;
      try {
        if (!document.hidden) {
          const response = await apiWrite<{ articles: Article[]; sources?: ResearchSource[] }>('/api/ai/research/sources/', { urls: sources.map(source => source.url) });
          addArticles(response.articles);
          if (response.sources) addSources(response.sources);
          allStored = sources.every(source => source.status === 'stored');
        }
      } catch { /* A metadata refresh failure must not erase already found sources. */ }
      finally {
        polling = false;
        if (!controller.signal.aborted) {
          if (terminal && allStored) update({ enriching: false });
          else pollTimer = setTimeout(refreshMetadata, 5000);
        }
      }
    }
    async function run() {
      try {
        const config = await apiFetch<{ enabled: boolean }>('/api/ai/research/');
        if (controller.signal.aborted) return;
        if (!config.enabled) { update({ phase: 'disabled', message: 'Wyszukiwanie internetowe AI czeka na uruchomienie. Wyniki z naszej bazy są dostępne poniżej.' }); return; }
        update({ phase: 'searching', message: 'Rozpoczynam wyszukiwanie w źródłach…' });
        const csrf = await apiFetch<{ csrfToken: string }>('/api/auth/csrf/');
        if (controller.signal.aborted) return;
        deadlineTimer = setTimeout(() => {
          update({ phase: 'error', message: 'Wyszukiwanie trwało zbyt długo. Znalezione materiały pozostają dostępne.', enriching: false });
          controller.abort();
        }, 160_000);
        const response = await fetch('/api/ai/research/stream/', {
          method: 'POST', credentials: 'include', cache: 'no-store', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', 'X-CSRFToken': csrf.csrfToken },
          body: JSON.stringify({ query, mode: 'context', request_id: crypto.randomUUID() }),
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || 'Nie udało się rozpocząć wyszukiwania zewnętrznego.');
        }
        await readResearchStream(response, ({ event, data }) => {
          if (event === 'progress') {
            const { stage } = data as { stage: string };
            update({ message: stage === 'completed' ? 'Odebrano odpowiedź wyszukiwarki. Sprawdzam odniesienia…' : 'Przeszukuję internet w obrębie naszej listy źródeł…' });
          } else if (event === 'sources') {
            addSources((data as { sources: ResearchSource[] }).sources);
            update({ enriching: true });
            if (!pollTimer && !polling) pollTimer = setTimeout(refreshMetadata, 1000);
          } else if (event === 'metadata') {
            addArticles((data as { articles: Article[] }).articles);
          } else if (event === 'result') {
            const result = data as ResearchResult;
            addSources(result.sources);
            addArticles(Object.values(result.archive_timeline).flat());
            update({ result });
          } else if (event === 'error') {
            terminal = true;
            update({ phase: 'error', message: (data as { detail: string }).detail });
          } else if (event === 'done') {
            sawDone = true; terminal = true;
            if ((data as { status: string }).status === 'completed') update({ phase: 'completed', message: 'Wyszukiwanie zakończone. To znalezione odniesienia, nie pełne archiwum tematu.' });
          }
        }, controller.signal);
        if (!controller.signal.aborted && !sawDone) throw new Error('Połączenie zostało przerwane. Zachowaliśmy już znalezione odnośniki.');
      } catch (error) {
        terminal = true;
        update({ phase: 'error', message: error instanceof Error ? error.message : 'Wyszukiwanie internetowe jest chwilowo niedostępne.' });
      } finally {
        if (deadlineTimer) clearTimeout(deadlineTimer);
      }
    }
    // Defer dispatch so React development remounts cannot spend the budget twice.
    const startTimer = setTimeout(run, 100);
    return () => {
      clearTimeout(startTimer); clearTimeout(pollTimer); clearTimeout(deadlineTimer);
      controller.abort();
    };
  }, [query, attempt]);
  const current = state.query === query ? state : initial(query);
  return {
    ...current, busy: current.phase === 'checking' || current.phase === 'searching',
    stop: () => { active.current?.abort(); setState(previous => ({ ...previous, phase: 'stopped', message: 'Wyszukiwanie zatrzymane. Znalezione materiały pozostają dostępne.', enriching: false })); },
    retry: () => setAttempt(previous => previous + 1),
  };
}
