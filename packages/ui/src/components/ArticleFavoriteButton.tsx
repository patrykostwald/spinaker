"use client";

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { setArticleFavorite, useArticleFavorites, useOwnerId } from '../lib/personal';
import { AccountDialog } from './AccountDialog';
import { Button } from '../kit';

/**
 * Dyskretne wejście do ulubionych materiałów.
 * `compact` — ikona na boxie, widoczna tylko dla zalogowanych (strona publiczna pozostaje bez zmian).
 */
export function ArticleFavoriteButton({ articleId, title, compact = false }: { articleId: number; title: string; compact?: boolean }) {
  const { ownerId } = useOwnerId();
  const favorites = useArticleFavorites();
  const cache = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [loginOpen, setLoginOpen] = useState(false);
  const saved = Boolean(favorites.data?.results.some(row => row.article.id === articleId));
  const unavailable = favorites.isError;

  if (compact && (!ownerId || unavailable)) return null;

  async function toggle() {
    if (!ownerId) { setLoginOpen(true); return; }
    setPending(true); setError('');
    try { await setArticleFavorite(cache, ownerId, articleId, !saved); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Nie udało się zmienić ulubionych.'); }
    finally { setPending(false); }
  }

  const label = `${saved ? 'Usuń z ulubionych materiałów' : 'Dodaj do ulubionych materiałów'}: ${title}`;
  if (compact) {
    return (
      <>
        <Button type="button" shape="icon" variant="quiet" size="sm" className="sc-favorite-dot" pressed={saved} aria-label={label} title={saved ? 'W ulubionych' : 'Dodaj do ulubionych'}
          disabled={pending || favorites.isPending} onClick={toggle} iconStart={<span aria-hidden="true">{saved ? '♥' : '♡'}</span>} />
        {error && <span role="alert" className="sr-only">{error}</span>}
      </>
    );
  }
  return (
    <span className="sc-favorite-control">
      <Button type="button" variant="quiet" size="sm" className="sc-favorite-button" pressed={saved} aria-label={label}
        disabled={pending || Boolean(ownerId && favorites.isPending) || unavailable} onClick={toggle}>
        <span aria-hidden="true">{saved ? '♥' : '♡'}</span> {saved ? 'W ulubionych' : 'Zapisz materiał'}
      </Button>
      {unavailable && <small>Ulubione materiały są w trakcie udostępniania.</small>}
      {error && <small role="alert" className="sc-account-error">{error}</small>}
      {loginOpen && <AccountDialog open={loginOpen} onClose={() => setLoginOpen(false)} />}
    </span>
  );
}
